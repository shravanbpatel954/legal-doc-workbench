import hashlib

import pymupdf
import pytesseract
from django.conf import settings
from PIL import Image


def sha256_of(data):
    return hashlib.sha256(data).hexdigest()

def check_pdf(filename, data):
    limit_mb = settings.MAX_UPLOAD_SIZE_MB

    if not filename.lower().endswith(".pdf"):
        raise ValueError("Only .pdf files are accepted.")
    if not data:
        raise ValueError("The file is empty.")
    if len(data) > limit_mb * 1024 * 1024:
        raise ValueError(f"The file is too large (limit is {limit_mb:g} MB).")
    if not data.lstrip().startswith(b"%PDF-"):
        raise ValueError("This is not a real PDF. The content is not PDF data.")

    try:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise ValueError("The PDF is corrupt or cannot be read.")

    with pdf:
        if pdf.needs_pass:
            raise ValueError("The PDF is password protected. Remove the password and upload it again.")
        if pdf.page_count == 0:
            raise ValueError("The PDF has no readable pages.")
        return pdf.page_count


def page_needs_ocr(text):
    useful = sum(ch.isalnum() for ch in text)
    return useful < settings.OCR_MIN_CHARS


def ocr_page(page):
    """OCR one PDF page. Returns (text, average confidence or None)."""
    pix = page.get_pixmap(dpi=settings.OCR_DPI)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    data = pytesseract.image_to_data(image, lang=settings.OCR_LANG, output_type=pytesseract.Output.DICT)

    lines = {}
    scores = []
    for i, word in enumerate(data["text"]):
        word = word.strip()
        conf = float(data["conf"][i])
        if not word or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
        scores.append(conf)

    text = "\n".join(" ".join(words) for words in lines.values())
    confidence = round(sum(scores) / len(scores), 1) if scores else None
    return text, confidence


def first_page_text(data):
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            page = pdf[0]
            text = page.get_text()
            if page_needs_ocr(text):
                text, _ = ocr_page(page)
            return text
    except Exception:
        return ""
