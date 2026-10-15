import threading
import time

import pymupdf
from django.conf import settings
from django.db import connection
from django.db.models import Count, Q

from .keywords import top_keywords
from .models import Document, DocumentPage, Keyword
from .pdf_utils import ocr_page, page_needs_ocr


def start_processing(document):
    Document.objects.filter(pk=document.pk).update(status=Document.Status.QUEUED)
    if settings.PROCESS_IN_BACKGROUND:
        threading.Thread(target=_in_thread, args=(document.pk,), daemon=True).start()
    else:
        process_document(document.pk)


def _in_thread(document_id):
    try:
        process_document(document_id)
    finally:
        connection.close()  # threads get their own connection


def process_document(document_id):
    document = Document.objects.get(pk=document_id)
    Document.objects.filter(pk=document.pk).update(status=Document.Status.PROCESSING)

    have = set(document.pages.values_list("page_number", flat=True))
    DocumentPage.objects.bulk_create(
        DocumentPage(document=document, page_number=n)
        for n in range(1, document.page_count + 1)
        if n not in have
    )

    try:
        pdf = pymupdf.open(document.file.path)
    except Exception:
        Document.objects.filter(pk=document.pk).update(status=Document.Status.FAILED)
        return

    with pdf:
        todo = document.pages.exclude(processing_status=DocumentPage.Status.COMPLETED)
        for number in list(todo.values_list("page_number", flat=True)):
            process_page(document, number, pdf)
            refresh_progress(document)

    save_keywords(document)


def process_page(document, number, pdf=None):
    """Extract one page. If it fails the error is stored on that page so only it needs a retry."""
    row = DocumentPage.objects.get(document=document, page_number=number)
    row.processing_status = DocumentPage.Status.PROCESSING
    row.save(update_fields=["processing_status"])

    started = time.monotonic()
    own_pdf = pdf is None
    try:
        if own_pdf:
            pdf = pymupdf.open(document.file.path)
        page = pdf[number - 1]

        text = page.get_text()
        if page_needs_ocr(text):
            text, row.ocr_confidence = ocr_page(page)
            row.extraction_method = DocumentPage.Method.OCR
        else:
            row.ocr_confidence = None
            row.extraction_method = DocumentPage.Method.TEXT

        row.ocr_text = text
        row.error_message = ""
        row.processing_status = DocumentPage.Status.COMPLETED
    except Exception as error:
        row.error_message = str(error) or error.__class__.__name__
        row.processing_status = DocumentPage.Status.FAILED
    finally:
        if own_pdf and pdf is not None:
            pdf.close()

    row.processing_time = round(time.monotonic() - started, 2)
    # corrected_text is left out on purpose
    row.save(update_fields=[
        "extraction_method", "ocr_text", "ocr_confidence",
        "processing_status", "error_message", "processing_time",
    ])
    return row


def refresh_progress(document):
    """Recount the pages and set the document's progress and status."""
    done_states = [DocumentPage.Status.COMPLETED, DocumentPage.Status.FAILED]
    counts = document.pages.aggregate(
        done=Count("pk", filter=Q(processing_status__in=done_states)),
        failed=Count("pk", filter=Q(processing_status=DocumentPage.Status.FAILED)),
    )
    done, failed = counts["done"], counts["failed"]

    if done < document.page_count:
        status = Document.Status.PROCESSING
    elif failed == 0:
        status = Document.Status.COMPLETED
    elif failed == done:
        status = Document.Status.FAILED
    else:
        status = Document.Status.PARTIAL_FAILURE

    Document.objects.filter(pk=document.pk).update(pages_processed=done, status=status)


def save_keywords(document):
    text = " ".join(page.text for page in document.pages.all())
    words = top_keywords(text)
    document.keywords.set([Keyword.objects.get_or_create(word=w)[0] for w in words])
