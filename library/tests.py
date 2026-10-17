import datetime
from django.test import TestCase, Client
from django.utils import timezone
from .models import Company, Document, DocumentType, DocumentPage
from .forms import SearchForm
from .search import search_documents


class SearchAndFilterTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Corp")
        self.doc_type = DocumentType.objects.create(name="Agreement")
        self.doc_today = Document.objects.create(
            title="Today Doc",
            original_filename="today.pdf",
            file_size_kb=10,
            sha256="dummy_sha_today",
            company=self.company,
            document_type=self.doc_type,
            page_count=1,
            pages_processed=1,
            status=Document.Status.COMPLETED,
        )

    def test_search_form_date_range_fields(self):
        today_str = timezone.localdate().isoformat()
        form = SearchForm({"date_from": today_str, "date_to": today_str})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["date_from"], timezone.localdate())
        self.assertEqual(form.cleaned_data["date_to"], timezone.localdate())

    def test_search_by_date_range(self):
        today = timezone.localdate()
        results = search_documents({"date_from": today, "date_to": today})
        self.assertIn(self.doc_today, results)

        tomorrow = today + datetime.timedelta(days=1)
        results_future = search_documents({"date_from": tomorrow})
        self.assertNotIn(self.doc_today, results_future)

    def test_search_by_status(self):
        results = search_documents({"status": Document.Status.COMPLETED})
        self.assertIn(self.doc_today, results)

        results_failed = search_documents({"status": Document.Status.FAILED})
        self.assertNotIn(self.doc_today, results_failed)

    def test_search_by_company(self):
        results = search_documents({"company": self.company.pk})
        self.assertIn(self.doc_today, results)

    def test_index_view_renders_date_range(self):
        client = Client()
        today_str = timezone.localdate().isoformat()
        response = client.get("/", {"date_from": today_str, "date_to": today_str}, SERVER_NAME="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="date_from"')
        self.assertContains(response, 'name="date_to"')
        self.assertContains(response, "Today Doc")
