from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .detect import guess_details
from .forms import DetailsForm, SearchForm, UploadForm, check_upload
from .models import Company, Document, DocumentPage, DocumentType
from .pdf_utils import first_page_text
from .processing import process_page, refresh_progress, save_keywords, start_processing
from .search import add_page_hits, page_has_text, search_documents

PER_PAGE = 10
NAV_BLOCK = 60  # page numbers shown at a time in the page navigator


def paginate(request, items, per_page=PER_PAGE):
    """One page of items, plus the current query string without ?page= for the pager links."""
    page = Paginator(items, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()


def index(request):
    """The main page: the document list and the search are the same thing."""
    form = SearchForm(request.GET)
    filters = form.cleaned_data if form.is_valid() else {}

    page, querystring = paginate(request, search_documents(filters))
    documents = list(page.object_list)
    add_page_hits(documents, filters)
    page.object_list = documents

    return render(request, "index.html", {
        "form": form,
        "page": page,
        "querystring": querystring,
        "term": filters.get("q", ""),
        "searching": any(request.GET.get(name) for name in form.fields),
    })


def form_page(request, form, document=None):
    """Upload and edit share one screen. The lists feed the company/type suggestions."""
    return render(request, "document_form.html", {
        "form": form,
        "document": document,
        "companies": Company.objects.all(),
        "types": DocumentType.objects.all(),
    })


def upload(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save()
        start_processing(document)
        messages.success(request, "Uploaded. The pages are being read now.")
        return redirect("document", document.pk)
    return form_page(request, form)


@require_POST
def upload_detect(request):
    """Called by the upload page as soon as a file is chosen: check it and guess its details."""
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "No file was received."})

    data = upload.read()
    try:
        page_count, _ = check_upload(upload.name, data)
    except ValueError as error:
        return JsonResponse({"error": str(error)})

    guess = guess_details(
        first_page_text(data),
        upload.name,
        companies=list(Company.objects.values_list("name", flat=True)),
        types=list(DocumentType.objects.values_list("name", flat=True)),
    )
    return JsonResponse({"pages": page_count, **guess})


def edit_details(request, pk):
    document = get_object_or_404(Document, pk=pk)
    initial = {
        "title": document.title,
        "company": document.company.name,
        "document_type": document.document_type.name,
    }
    form = DetailsForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.apply_to(document)
        document.save()
        messages.success(request, "Details saved.")
        return redirect("document", document.pk)
    return form_page(request, form, document)


@require_POST
def delete_document(request, pk):
    document = get_object_or_404(Document, pk=pk)
    if not check_password(request.POST.get("password", ""), settings.DOCUMENT_DELETE_PASSWORD_HASH):
        messages.error(request, "Incorrect password. The document was not deleted.")
        return redirect("index")

    file_name = document.file.name
    storage = document.file.storage
    try:
        with transaction.atomic():
            document.delete()
            storage.delete(file_name)
    except OSError:
        messages.error(request, "The PDF could not be removed, so the document and extracted data were not deleted.")
        return redirect("index")

    messages.success(request, "The PDF and its extracted data were permanently deleted.")
    return redirect("index")


def queue(request):
    """Everything that is not finished yet, or had a problem."""
    waiting = Document.objects.exclude(status=Document.Status.COMPLETED).select_related("company")
    page, querystring = paginate(request, waiting, per_page=25)
    return render(request, "queue.html", {
        "page": page,
        "querystring": querystring,
        "refresh": any(doc.is_working for doc in page),
    })


def document(request, pk, number=None):
    """Document details and page review on one screen."""
    doc = get_object_or_404(Document.objects.select_related("company", "document_type"), pk=pk)
    term = request.GET.get("q", "").strip()
    number = number or 1
    if number > max(doc.page_count, 1):
        raise Http404("No such page")

    page = doc.pages.filter(page_number=number).first()  # missing until reading has started

    if request.method == "POST" and page:
        if "revert" in request.POST:
            page.corrected_text, page.is_corrected = "", False
            messages.success(request, "Back to the extracted text.")
        else:
            page.corrected_text, page.is_corrected = request.POST.get("text", ""), True
            messages.success(request, "Your changes are saved.")
        page.save(update_fields=["corrected_text", "is_corrected"])
        save_keywords(doc)
        return redirect("document_page", doc.pk, number)

    hits = set()
    if term:
        hits = set(doc.pages.filter(page_has_text(term)).values_list("page_number", flat=True))

    first = (number - 1) // NAV_BLOCK * NAV_BLOCK + 1
    last = min(first + NAV_BLOCK - 1, doc.page_count)
    tiles = [
        {"number": row["page_number"], "status": row["processing_status"].lower(),
         "hit": row["page_number"] in hits}
        for row in doc.pages.filter(page_number__range=(first, last)).values("page_number", "processing_status")
    ]

    return render(request, "document.html", {
        "doc": doc,
        "page": page,
        "number": number,
        "term": term,
        "editing": "edit" in request.GET,
        "tiles": tiles,
        "block_before": first - NAV_BLOCK if first > 1 else None,
        "block_after": last + 1 if last < doc.page_count else None,
        "next_match": min((n for n in hits if n > number), default=None),
        "match_count": len(hits),
        "failed_count": doc.pages.filter(processing_status=DocumentPage.Status.FAILED).count(),
    })


def page_retry(request, pk, number):
    doc = get_object_or_404(Document, pk=pk)
    if request.method == "POST":
        process_page(doc, number)
        refresh_progress(doc)
        save_keywords(doc)
        messages.success(request, f"Page {number} was read again.")
    return redirect("document_page", doc.pk, number)


def document_pdf(request, pk):
    """Serve the original PDF through the app, so file paths are never shown to the browser."""
    doc = get_object_or_404(Document, pk=pk)
    return FileResponse(doc.file.open("rb"), content_type="application/pdf", filename=doc.original_filename)
