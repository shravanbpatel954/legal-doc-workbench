from django.contrib import admin

from .models import Company, Document, DocumentPage, DocumentType, Keyword

admin.site.register(Company)
admin.site.register(DocumentType)
admin.site.register(Keyword)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "company", "document_type", "page_count", "status"]
    list_filter = ["status", "company", "document_type"]


@admin.register(DocumentPage)
class DocumentPageAdmin(admin.ModelAdmin):
    list_display = ["document", "page_number", "extraction_method", "processing_status", "is_corrected"]
    list_filter = ["processing_status", "extraction_method"]
