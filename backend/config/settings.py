import os
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
DEBUG = os.getenv("CRM_DEBUG", "1") == "1"
SECRET_KEY = os.getenv("CRM_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Задайте CRM_SECRET_KEY перед запуском.")
    SECRET_KEY = secrets.token_urlsafe(48)

ALLOWED_HOSTS = os.getenv("CRM_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(
    ","
)
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "crm",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "crm.middleware.PrivateResponseMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "crm.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
if os.getenv("CRM_DB_ENGINE", "sqlite") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("CRM_DB_NAME", "rehubpro_crm"),
            "USER": os.getenv("CRM_DB_USER", "rehubpro_crm"),
            "PASSWORD": os.environ["CRM_DB_PASSWORD"],
            "HOST": os.getenv("CRM_DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("CRM_DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    if not DEBUG:
        raise ImproperlyConfigured("Для рабочего окружения используйте PostgreSQL.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_NAME = "rehubcrm_session"
CSRF_COOKIE_NAME = "rehubcrm_csrf"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = os.getenv(
    "CRM_TRUSTED_ORIGINS", "http://127.0.0.1:3100,http://localhost:3100"
).split(",")
CSRF_FAILURE_VIEW = "crm.views.csrf_failure"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = not DEBUG
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024
FRONTEND_URL = os.getenv("CRM_FRONTEND_URL", "http://127.0.0.1:3100").rstrip("/")
EMAIL_BACKEND = os.getenv(
    "CRM_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("CRM_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("CRM_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("CRM_EMAIL_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("CRM_EMAIL_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("CRM_EMAIL_TLS", "1") == "1"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv("CRM_FROM_EMAIL", "RehubPro CRM <noreply@localhost>")
if not DEBUG and EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
    raise ImproperlyConfigured("Для рабочего окружения настройте отправку почты SMTP.")
PASSWORD_RESET_TIMEOUT = 60 * 60

# Ключ шифрования хранится отдельно от базы и должен сохраняться при переносе CRM.
INTEGRATION_ENCRYPTION_KEY = os.getenv("CRM_INTEGRATION_KEY", "")
CENTER_ALLOWED_DOMAINS = tuple(
    x.strip().lower()
    for x in os.getenv("CRM_CENTER_ALLOWED_DOMAINS", "rehubpro.kz").split(",")
    if x.strip()
)
