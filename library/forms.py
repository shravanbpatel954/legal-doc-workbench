from pathlib import Path
from django import forms
from .models import Company, Document, DocumentType
from .pdf_utils import check_pdf, sha256_of

def clean_name(value):
    return " ".join(value.split())

def get_or_create_named(model, name):
    name = clean_name(name)
    return model.objects.filter(name__iexact=name).first() or model.objects.create(name=name)

def check_upload(filename, data):
    page_count = check_pdf(filename, data)
    sha256 = sha256_of(data)
    same = Document.objects.filter(sha256=sha256).first()
    if same:
        raise ValueError(f'This file is already in the system as "{same.title}" (document {same.pk}).')
    return page_count, sha256

class DetailsForm(forms.Form):
    title = forms.CharField(max_length=255)
    company = forms.CharField(max_length=200, widget=forms.TextInput(attrs={
        "list": "company-options", "placeholder": "Pick one or type a new company", "autocomplete": "off"}))
    document_type = forms.CharField(max_length=100, label="Document type", widget=forms.TextInput(attrs={
        "list": "type-options", "placeholder": "Pick one or type a new type", "autocomplete": "off"}))
    def clean_title(self):
        return clean_name(self.cleaned_data["title"])

    def clean_company(self):
        return clean_name(self.cleaned_data["company"])

    def clean_document_type(self):
        return clean_name(self.cleaned_data["document_type"])

    def apply_to(self, document):
        document.title = self.cleaned_data["title"]
        document.company = get_or_create_named(Company, self.cleaned_data["company"])
        document.document_type = get_or_create_named(DocumentType, self.cleaned_data["document_type"])

class UploadForm(DetailsForm):
    field_order = ["file", "title", "company", "document_type"]
    title = forms.CharField(max_length=255, required=False)
    file = forms.FileField(label="PDF file", widget=forms.FileInput(attrs={"accept": ".pdf,application/pdf"}))

    def clean(self):
        cleaned_data = super().clean()
        upload = cleaned_data.get("file")
        if upload and not cleaned_data.get("title"):
            try:
                title = self.fields["title"].clean(Path(upload.name).stem)
                cleaned_data["title"] = clean_name(title)
            except forms.ValidationError as error:
                self.add_error("title", error)
        return cleaned_data

    def clean_file(self):
        upload = self.cleaned_data["file"]
        data = upload.read()
        upload.seek(0)
        try:
            self.page_count, self.sha256 = check_upload(upload.name, data)
        except ValueError as error:
            raise forms.ValidationError(str(error))
        self.size = len(data)
        return upload

    def save(self):
        upload = self.cleaned_data["file"]
        document = Document(
            file=upload,
            original_filename=upload.name,
            file_size_kb=max(1, self.size // 1024),
            sha256=self.sha256,
            page_count=self.page_count,
        )
        self.apply_to(document)
        document.save()
        return document


class SearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    company = forms.ModelChoiceField(Company.objects.all(), required=False, empty_label="All companies")
    document_type = forms.ModelChoiceField(DocumentType.objects.all(), required=False, empty_label="All types")
    status = forms.ChoiceField(required=False, label="Status",
                               choices=[("", "Any status")] + Document.Status.choices)
    date_from = forms.DateField(required=False, label="From",
                                widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, label="To",
                              widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs.update({
            "placeholder": "Search by title, file name, company, type, keyword, or words inside the pages",
            "autofocus": True,
        })
        for name in ("company", "document_type", "status", "date_from", "date_to"):
            self.fields[name].widget.attrs["onchange"] = "this.form.submit()"
