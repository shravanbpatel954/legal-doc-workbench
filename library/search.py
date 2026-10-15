"""Everything about searching. Views hand in the cleaned search form, and get back querysets."""
import re

from django.db.models import Count, Exists, OuterRef, Q

from .models import Document, DocumentPage, Keyword


def page_has_text(term):
    """Match the corrected text when somebody fixed the page, otherwise the OCR text."""
    return (
        Q(is_corrected=False, ocr_text__icontains=term)
        | Q(is_corrected=True, corrected_text__icontains=term)
    )


def search_documents(filters):
    """Documents matching the search box and all the filters.

    The search text is looked for in the title, file name, company, type, keywords,
    the document id and in the text of every page.
    """
    docs = Document.objects.select_related("company", "document_type").prefetch_related("keywords")

    if filters.get("company"):
        docs = docs.filter(company=filters["company"])
    if filters.get("document_type"):
        docs = docs.filter(document_type=filters["document_type"])
    if filters.get("status"):
        docs = docs.filter(status=filters["status"])
    term = filters.get("q")
    if term:
        matches = (
            Q(title__icontains=term)
            | Q(original_filename__icontains=term)
            | Q(company__name__icontains=term)
            | Q(document_type__name__icontains=term)
            | Exists(Keyword.objects.filter(document=OuterRef("pk"), word__icontains=term))
            | Exists(DocumentPage.objects.filter(page_has_text(term), document=OuterRef("pk")))
        )
        if term.isdigit():
            matches |= Q(pk=int(term))
        docs = docs.filter(matches)

    return docs


def matching_pages(filters):
    """Pages whose text contains the search text. Empty when nothing was typed."""
    term = filters.get("q")
    if not term:
        return DocumentPage.objects.none()
    return DocumentPage.objects.filter(page_has_text(term))


def add_page_hits(documents, filters, show=3):
    """Put the first few matching pages on each document, ready for the template.

    Sets doc.hits (pages with a .snippet) and doc.more_hits (how many are not shown).
    """
    term = filters.get("q")
    pages = matching_pages(filters).filter(document__in=documents)
    totals = dict(pages.values_list("document_id").annotate(n=Count("pk")).order_by())

    for doc in documents:
        doc.hits = []
        doc.more_hits = 0
        total = totals.get(doc.pk, 0)
        if not total:
            continue
        doc.hits = list(pages.filter(document=doc)[:show])
        for page in doc.hits:
            page.snippet = make_snippet(page.text, term)
        doc.more_hits = total - len(doc.hits)


def make_snippet(text, term, width=80):
    """A short piece of the page around the first match."""
    text = re.sub(r"\s+", " ", text).strip()
    at = text.lower().find(term.lower()) if term else -1
    if at == -1:
        return text[:2 * width]

    start = max(0, at - width)
    end = min(len(text), at + len(term) + width)
    return ("..." if start else "") + text[start:end] + ("..." if end < len(text) else "")
