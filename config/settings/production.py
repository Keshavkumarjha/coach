# ruff: noqa: E501
from __future__ import annotations

from .base import *  # noqa: F403
from .base import DATABASES, INSTALLED_APPS, REDIS_URL, SPECTACULAR_SETTINGS, env  # noqa: F401

# ------------------------------------------------------------------------------
# GENERAL
# ------------------------------------------------------------------------------
DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["coachmaster.in", "www.coachmaster.in"],
)

# If you are behind nginx / load balancer:
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ------------------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------------------
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

# Django 4.2+ (safe to keep; ignored in older versions)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True


# ------------------------------------------------------------------------------
# CACHES (Redis)
# ------------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # Avoid hard failures if redis temporarily down
            "IGNORE_EXCEPTIONS": True,
        },
    },
}


# ------------------------------------------------------------------------------
# SECURITY (HARDENED)
# ------------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# If you ever use cookies (admin etc.)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

SESSION_COOKIE_NAME = "__Secure-sessionid"
CSRF_COOKIE_NAME = "__Secure-csrftoken"

# Modern recommended settings
SECURE_CONTENT_TYPE_NOSNIFF = env.bool("DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True)
SECURE_REFERRER_POLICY = env("DJANGO_SECURE_REFERRER_POLICY", default="same-origin")

# Clickjacking protection
X_FRAME_OPTIONS = "DENY"

# CSP is best added via django-csp; leaving out here since you didn’t install it.

# HSTS rollout:
# Start with 60 seconds, then 1 day, then 6 months+ once verified.
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)

# Cross-origin opener policy (protects from tabnabbing)
SECURE_CROSS_ORIGIN_OPENER_POLICY = env(
    "DJANGO_SECURE_CROSS_ORIGIN_OPENER_POLICY",
    default="same-origin",
)

# ------------------------------------------------------------------------------
# CORS / CSRF TRUST
# ------------------------------------------------------------------------------
# If frontend calls API from these domains:
CORS_ALLOWED_ORIGINS = env.list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    default=[
        "https://coachmaster.in",
        "https://www.coachmaster.in",
    ],
)

# Required for CSRF in some cases; safe to set anyway
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[
        "https://coachmaster.in",
        "https://www.coachmaster.in",
    ],
)

# If you use Authorization header (JWT), allow it:
CORS_ALLOW_HEADERS = env.list(
    "DJANGO_CORS_ALLOW_HEADERS",
    default=[
        "accept",
        "accept-encoding",
        "authorization",
        "content-type",
        "dnt",
        "origin",
        "user-agent",
        "x-csrftoken",
        "x-requested-with",
    ],
)

CORS_ALLOW_CREDENTIALS = env.bool("DJANGO_CORS_ALLOW_CREDENTIALS", default=False)


# ------------------------------------------------------------------------------
# STATIC & MEDIA (S3 via django-storages)
# ------------------------------------------------------------------------------
# Make sure you installed:
# pip install django-storages[boto3] collectfasta
INSTALLED_APPS += ["storages"]

AWS_ACCESS_KEY_ID = env("DJANGO_AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("DJANGO_AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("DJANGO_AWS_STORAGE_BUCKET_NAME")

AWS_QUERYSTRING_AUTH = False

AWS_S3_REGION_NAME = env("DJANGO_AWS_S3_REGION_NAME", default=None)
AWS_S3_CUSTOM_DOMAIN = env("DJANGO_AWS_S3_CUSTOM_DOMAIN", default=None)

aws_s3_domain = AWS_S3_CUSTOM_DOMAIN or f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

_AWS_EXPIRY = 60 * 60 * 24 * 7  # 7 days

AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": f"max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate",
}

AWS_S3_MAX_MEMORY_SIZE = env.int("DJANGO_AWS_S3_MAX_MEMORY_SIZE", default=100_000_000)  # 100MB

# Django 4.2+ storage config:
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {"location": "media", "file_overwrite": False},
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {"location": "static"},
    },
}

MEDIA_URL = f"https://{aws_s3_domain}/media/"
STATIC_URL = f"https://{aws_s3_domain}/static/"

# collectfasta (optional; speeds collectstatic with S3)
INSTALLED_APPS = ["collectfasta", *INSTALLED_APPS]
COLLECTFASTA_STRATEGY = "collectfasta.strategies.boto3.Boto3Strategy"


# ------------------------------------------------------------------------------
# EMAIL
# ------------------------------------------------------------------------------
DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default="coachmaster <noreply@coachmaster.in>",
)
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = env("DJANGO_EMAIL_SUBJECT_PREFIX", default="[coachmaster] ")

EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=True)
EMAIL_TIMEOUT = env.int("DJANGO_EMAIL_TIMEOUT", default=10)

# Optional: Anymail (only if you use it)
if env.bool("DJANGO_USE_ANYMAIL", default=False):
    INSTALLED_APPS += ["anymail"]
    ANYMAIL = {}  # configure provider keys in env


# ------------------------------------------------------------------------------
# ADMIN
# ------------------------------------------------------------------------------
ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")


# ------------------------------------------------------------------------------
# LOGGING (production safe)
# ------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(name)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "django.request": {"handlers": ["mail_admins"], "level": "ERROR", "propagate": True},
        "django.security.DisallowedHost": {"handlers": ["console", "mail_admins"], "level": "ERROR", "propagate": True},
    },
}


# ------------------------------------------------------------------------------
# DRF SPECTACULAR - set correct server
# ------------------------------------------------------------------------------
SPECTACULAR_SETTINGS["SERVERS"] = [
    {"url": "https://coachmaster.in", "description": "Production server"},
]