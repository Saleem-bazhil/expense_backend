"""
Django settings for Expense Tracker project.
"""
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in ('1', 'true', 'yes', 'on')


def env_list(name: str, default: str = '') -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


def normalize_host(value: str) -> str:
    value = value.strip()
    if not value:
        return ''
    if value == '*':
        return value

    parsed = urlsplit(value if '://' in value else f'//{value}')
    host = parsed.hostname or value
    return host.strip('[]')


def env_hosts(name: str, default: str = '') -> list[str]:
    return [host for item in env_list(name, default) if (host := normalize_host(item))]


def normalize_origin(value: str) -> str:
    value = value.strip().rstrip('/')
    if not value:
        return ''

    parsed = urlsplit(value if '://' in value else f'https://{value}')
    if not parsed.netloc:
        return ''
    return f'{parsed.scheme}://{parsed.netloc}'


def env_origins(name: str, default: str = '') -> list[str]:
    return [origin for item in env_list(name, default) if (origin := normalize_origin(item))]


# Core
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production')
DEBUG = env_bool('DJANGO_DEBUG', False)
ALLOWED_HOSTS = env_hosts('DJANGO_ALLOWED_HOSTS', '*' if DEBUG else 'localhost,127.0.0.1')

# Behind a proxy (Dokploy/Traefik) — trust X-Forwarded-Proto
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = env_bool('DJANGO_USE_X_FORWARDED_HOST', False)

# CSRF trusted origins: full scheme+host, comma-separated
# e.g. "https://api.example.com,https://admin.example.com"
CSRF_TRUSTED_ORIGINS = env_origins('DJANGO_CSRF_TRUSTED_ORIGINS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'corsheaders',
    'django_filters',
    # Local
    'expenses',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database — PostgreSQL when DB_ENGINE=postgres, else SQLite fallback
if os.getenv('DB_ENGINE', 'sqlite').lower() in ('postgres', 'postgresql'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'expense_tracker'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
            'CONN_HEALTH_CHECKS': True,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('DJANGO_TIME_ZONE', 'Asia/Kolkata')
USE_I18N = True
USE_TZ = True

# Static files (WhiteNoise serves them from STATIC_ROOT in production)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS — allow specific origins in production; wildcard only when explicitly set
CORS_ALLOW_ALL_ORIGINS = env_bool('CORS_ALLOW_ALL_ORIGINS', DEBUG)
CORS_ALLOWED_ORIGINS = env_origins('CORS_ALLOWED_ORIGINS')

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# Production security toggles (only enforced when DEBUG=False and behind HTTPS)
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', False)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_SECURE_HSTS_SECONDS', '0'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'

# Logging to stdout (container-friendly)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
