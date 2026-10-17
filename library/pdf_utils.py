import hashlib
import os
import shutil

import pymupdf
import pytesseract
from django.conf import settings
from PIL import Image

_rapid_ocr = None


def _get_rapid_ocr():
    global _rapid_ocr
    if _rapid_ocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapid_ocr = RapidOCR()
        except Exception:
            _rapid_ocr = False
    return _rapid_ocr or None


def _find_tesseract_cmd():
    configured = getattr(settings, "TESSERACT_CMD", "")
    if configured and os.path.isfile(configured):
        return configured
    cmd = shutil.which("tesseract")
    if cmd:
        return cmd
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for path in common_paths:
        if os.path.isfile(path):
            return path
    return None


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
    pix = page.get_pixmap(dpi=settings.OCR_DPI)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    # 1. Try Tesseract if installed / configured
    tesseract_cmd = _find_tesseract_cmd()
    if tesseract_cmd:
        try:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
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
        except Exception:
            pass  # Fall back to RapidOCR

    # 2. Try RapidOCR (runs fully in Python / ONNX, no external installer needed)
    engine = _get_rapid_ocr()
    if engine is not None:
        import numpy as np
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
        result, _ = engine(img_array)
        if result:
            lines = []
            scores = []
            for item in result:
                text_str = str(item[1]).strip()
                if text_str:
                    lines.append(text_str)
                    scores.append(float(item[2]) * 100)

            text = "\n".join(lines)
            confidence = round(sum(scores) / len(scores), 1) if scores else None
            return text, confidence
        return "", None

    raise RuntimeError("No OCR engine available. Install Tesseract OCR or rapidocr-onnxruntime.")


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
