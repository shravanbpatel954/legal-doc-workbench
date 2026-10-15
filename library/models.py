import uuid

from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name


class DocumentType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Keyword(models.Model):
    word = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["word"]

    def __str__(self):
        return self.word


def pdf_path(instance, filename):
    # random name on disk, the real name is kept in original_filename
    return f"documents/{uuid.uuid4().hex}.pdf"


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        QUEUED = "QUEUED", "Queued"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        PARTIAL_FAILURE = "PARTIAL_FAILURE", "Partial failure"
        FAILED = "FAILED", "Failed"

    title = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=pdf_path)
    file_size_kb = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64, unique=True)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT)
    page_count = models.PositiveIntegerField(default=0)
    pages_processed = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    keywords = models.ManyToManyField(Keyword, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return self.title

    @property
    def is_working(self):
        return self.status in (self.Status.UPLOADED, self.Status.QUEUED, self.Status.PROCESSING)

    @property
    def progress(self):
        if not self.page_count:
            return 0
        return round(self.pages_processed * 100 / self.page_count)


class DocumentPage(models.Model):
    class Method(models.TextChoices):
        TEXT = "TEXT", "Digital text"
        OCR = "OCR", "OCR"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="pages")
    page_number = models.PositiveIntegerField()
    extraction_method = models.CharField(max_length=10, choices=Method.choices, blank=True)
    ocr_text = models.TextField(blank=True)
    ocr_confidence = models.FloatField(null=True, blank=True)
    processing_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    processing_time = models.FloatField(null=True, blank=True)  # seconds

    # A person's fix for bad OCR. Kept apart so a retry never wipes it.
    corrected_text = models.TextField(blank=True)
    is_corrected = models.BooleanField(default=False)

    class Meta:
        ordering = ["page_number"]
        constraints = [
            models.UniqueConstraint(fields=["document", "page_number"], name="one_row_per_page"),
        ]

    def __str__(self):
        return f"{self.document} / page {self.page_number}"

    @property
    def text(self):
        return self.corrected_text if self.is_corrected else self.ocr_text
