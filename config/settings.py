import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in {"1", "true", "yes"}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured.")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "accounts",
    "courses",
    "pathways",
    "certificates",
    "portfolios",
    "opportunities",
    "notifications",
    "learning_analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if os.getenv("DJANGO_TESTING") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ImproperlyConfigured(
            "DATABASE_URL must point to the Supabase PostgreSQL database."
        )
    use_transaction_pooler = (
        os.getenv("DATABASE_USE_TRANSACTION_POOLER", "False").lower()
        in {"1", "true", "yes"}
    )
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=0
            if use_transaction_pooler
            else int(os.getenv("DATABASE_CONN_MAX_AGE", "60")),
            conn_health_checks=True,
            ssl_require=True,
        )
    }
    if use_transaction_pooler:
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.UserJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.api_errors.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": "10/minute",
        "auth_register": "5/hour",
        "auth_role_selection": "5/hour",
        "password_reset": "5/hour",
        "student_verification_request": "5/hour",
        "student_verification_start": "5/hour",
        "student_verification_confirm": "10/hour",
        "email_change_request": "3/hour",
        "email_change_confirm": "10/hour",
        "oauth_authorize": "10/minute",
        "oauth_callback": "10/minute",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "USER_AUTHENTICATION_RULE": "accounts.auth_rules.user_authentication_rule",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "UCC SKILLSHUB API",
    "DESCRIPTION": "Learn • Practice • Grow — authentication, course learning, and skill pathway APIs.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = False

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_BUCKETS = {
    "profile_photos": os.getenv("SUPABASE_PROFILE_BUCKET", "profile-photos"),
    "project_attachments": os.getenv(
        "SUPABASE_PROJECT_BUCKET", "project-attachments"
    ),
    "course_resources": os.getenv("SUPABASE_COURSE_BUCKET", "course-resources"),
    "application_attachments": os.getenv(
        "SUPABASE_APPLICATION_BUCKET", "application-attachments"
    ),
}
SUPABASE_SIGNED_URL_TTL = int(os.getenv("SUPABASE_SIGNED_URL_TTL", "300"))
if not 1 <= SUPABASE_SIGNED_URL_TTL <= 3600:
    raise ImproperlyConfigured("SUPABASE_SIGNED_URL_TTL must be between 1 and 3600.")

FRONTEND_BASE_URL = os.getenv(
    "FRONTEND_URL", os.getenv("FRONTEND_BASE_URL", "")
).rstrip("/")
BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")
OAUTH_STATE_MAX_AGE = 600
STUDENT_VERIFICATION_CODE_TTL_SECONDS = 600
STUDENT_VERIFICATION_RESEND_COOLDOWN_SECONDS = 60
STUDENT_VERIFICATION_MAX_ATTEMPTS = 5
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in {"1", "true", "yes"}
EMAIL_TIMEOUT = 10
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
if not DEBUG and os.getenv("DJANGO_TESTING") != "1":
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "True").lower() in {
        "1",
        "true",
        "yes",
    }
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "pathways": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
