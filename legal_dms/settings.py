from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-only-key-change-in-production"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "library",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "legal_dms.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},  # the processing thread writes while pages are being viewed
    }
}

TIME_ZONE = "Asia/Kolkata"
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Uploaded PDFs are saved here. Only the relative path goes in the database.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---- Our own settings ----
MAX_UPLOAD_SIZE_MB = 50
DOCUMENT_DELETE_PASSWORD_HASH = "pbkdf2_sha256$1000000$WKytm5oj2ebJM3ccBGlt2v$ympOEAJE45MLQtbI8iBL9qKY9j2Hm/Jd/MAcxe9Enik="

# A page with fewer letters/digits than this is treated as scanned and sent to OCR.
OCR_MIN_CHARS = 20
OCR_DPI = 300
OCR_LANG = "eng"

# Leave empty if tesseract is on your PATH. On Windows, for example:
# TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_CMD = ""

# True: process in a background thread so the page count moves while you watch.
# False: process inside the request (the tests use this).
PROCESS_IN_BACKGROUND = True
