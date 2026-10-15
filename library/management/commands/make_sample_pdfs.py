from pathlib import Path

from django.core.management.base import BaseCommand

from library.sample_pdfs import CONTRACT, MORTGAGE, NOTICE, scanned_pdf, text_pdf


class Command(BaseCommand):
    help = "Create four small sample PDFs in the sample_pdfs folder."

    def handle(self, *args, **options):
        folder = Path("sample_pdfs")
        folder.mkdir(exist_ok=True)
        text_pdf(CONTRACT, folder / "service_agreement.pdf")
        text_pdf(NOTICE, folder / "legal_notice.pdf")
        text_pdf(MORTGAGE, folder / "mortgage_deed.pdf")
        scanned_pdf("SCANNED LETTER\n\nDear Sir,\nThe tenant agrees to pay the rent\non the first day of every month.",
                    folder / "scanned_letter.pdf")
        self.stdout.write(self.style.SUCCESS("Created 4 PDFs in the sample_pdfs folder. Upload them from the website."))
