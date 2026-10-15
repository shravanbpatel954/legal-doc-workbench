import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

from library.detect import TYPE_HINTS, guess_details
from library.forms import UploadForm
from library.models import Company, DocumentType
from library.pdf_utils import first_page_text
from library.processing import process_document
from library.sample_pdfs import CONTRACT, MORTGAGE, NOTICE, text_pdf

SAMPLES = {
    "service_agreement.pdf": CONTRACT,
    "legal_notice.pdf": NOTICE,
    "mortgage_deed.pdf": MORTGAGE,
}


class Command(BaseCommand):
    help = "Add the usual document types and three small sample documents, read like a real upload."

    def handle(self, *args, **options):
        for name in TYPE_HINTS:
            DocumentType.objects.get_or_create(name=name)

        with tempfile.TemporaryDirectory() as folder:
            for filename, pages in SAMPLES.items():
                path = Path(folder) / filename
                text_pdf(pages, path)
                data = path.read_bytes()

                # same steps as the upload screen: guess the details from the PDF, then save
                guess = guess_details(
                    first_page_text(data), filename,
                    companies=list(Company.objects.values_list("name", flat=True)),
                    types=list(DocumentType.objects.values_list("name", flat=True)),
                )
                form = UploadForm(guess, {"file": SimpleUploadedFile(filename, data, content_type="application/pdf")})
                if not form.is_valid():
                    self.stdout.write(f"Skipped {filename}: {form.errors.as_text()}")
                    continue
                document = form.save()
                process_document(document.pk)
                self.stdout.write(f"Added {document.title} ({document.company}, {document.document_type})")

        self.stdout.write(self.style.SUCCESS("Sample data is ready."))
