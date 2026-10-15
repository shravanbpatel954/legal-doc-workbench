# Legal Document Workbench

Upload legal PDFs, read them page by page (digital text, or OCR for scans), and search them.
Django + SQLite, plain CSS. No Node, no CDN, so it also works offline.

## Screens

| Screen | Address | What it does |
|---|---|---|
| Documents | `/` | The document list **and** the search. One box, a few filters. |
| Upload | `/upload/` | Choose a PDF; title, company and type are suggested from it. Upload time is recorded automatically. |
| Edit details | `/documents/<id>/edit/` | Change title, company and type later. Same form as upload. |
| Processing queue | `/queue/` | Documents still being read or with problems, with progress. |
| Document | `/documents/<id>/` | Details, page navigator, page text, edit, retry, next/previous. |

## Details from the PDF

When you choose a PDF on the upload screen, the page sends it to `/upload/detect/`. The server checks it
(real PDF, size, corrupt, password, duplicate) and reads the first page (OCR if it is a scan), then guesses:

- **Title**: the first real line of the page (or the file name).
- **Company**: a company already in the system that is named on the page; otherwise a name ending in
  Pvt Ltd, Private Limited, Limited, Ltd, LLP, LLC, Inc, Corp, Company or Bank.
- **Document type**: the type the page talks about most (mortgage, agreement, notice, invoice, ...). The list of
  words is `TYPE_HINTS` in `library/detect.py`. Types already in your database are matched as well.

These are only suggestions. Anything you have already typed is not overwritten, and everything can be changed.
The rules are plain Python in `library/detect.py` (no LLM) and are easy to extend.

## Company and type

Both are text boxes with a list of the names that already exist.

- Pick one from the list, or type a new name. A new name is **created when you save**, and shows up in the
  list (and in the search filters) from then on.
- Names are compared ignoring upper/lower case and extra spaces, so typing `acme  industries` reuses
  `Acme Industries` instead of making a copy.
- Nothing is created if the upload is rejected.

## Search (main page)

- The text is looked for in **title, file name, company, type, keywords, document ID and the text of every page**.
- Documents that match on page text show the matching pages with a highlighted snippet under the title.
  Click a snippet to open that page; "+ N more matching pages" opens the document with every match marked.
- The company, type and status dropdowns apply as soon as you change them. Keyword tags use the main search box.
- Several words are searched as an exact phrase (`property tax`, not "tax on property").

## Setup

1. Install Tesseract OCR (Windows: https://github.com/UB-Mannheim/tesseract/wiki).
   If it is not on your PATH, set `TESSERACT_CMD` in `legal_dms/settings.py`.
2. In this folder:

```
python -m venv env
env\Scripts\activate          (Linux/Mac: source env/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_sample_data
python manage.py createsuperuser
python manage.py runserver
```

3. Open http://127.0.0.1:8000

`seed_sample_data` adds the usual document types and three small sample documents, going through the same
detect-and-save steps as the upload screen. `make_sample_pdfs` writes four test PDFs (three digital, one scanned)
to `sample_pdfs/` so you can try the upload yourself. Run the tests with `python manage.py test`.

A migration file is included. If you change `models.py`, run `python manage.py makemigrations library`.

## Code layout

```
library/
  models.py        Company, DocumentType, Keyword, Document, DocumentPage
  detect.py        guesses company and type from the first page; title uses the filename
  forms.py         validates and saves upload/edit details and search filters
  search.py        all search and filter logic, no HTML in here
  keywords.py      removes common words and stores the 10 most frequent words as search tags
  processing.py    reads a PDF page by page, retry for one page
  pdf_utils.py     PDF checks, SHA-256, "does this page need OCR", the OCR call, first-page peek
  views.py         one function per screen
  templates/       base, index, document_form (upload + edit), queue, document, small pager
  static/library/style.css
```

## Notes

- Page rows follow the field names in the task spec: `document`, `page_number`, `ocr_text`,
  `ocr_confidence`, `processing_status`. A person's fix goes in `corrected_text` so an OCR retry never wipes it;
  search and keywords use the corrected text when there is one.
- A page is sent to OCR when it has fewer than `OCR_MIN_CHARS` letters/digits (`settings.py`).
- The upload checks extension, real PDF signature, size limit, corruption, password protection, and
  duplicates (SHA-256, whatever the file is called).
- The uploaded PDF's filename (without `.pdf`) is the default title; no title is extracted from page text.
- Use each document's **Delete** button to permanently remove the PDF and its extracted page data. The password is checked on the server; its hash is configured as `DOCUMENT_DELETE_PASSWORD_HASH` in `legal_dms/settings.py`.
- PDFs are opened through `/documents/<id>/pdf/`, so file paths on disk are never sent to the browser.
- The file is sent to the server twice on upload: once to read its details, once when you press Upload.
- Search uses `icontains`, fine for a prototype. For large volumes move the page text to PostgreSQL
  full-text search or a search engine; only `search.py` would change.
- Reading runs in a background thread (`PROCESS_IN_BACKGROUND`). `process_document` and `process_page`
  do not depend on the views, so they can be moved to Celery later.
