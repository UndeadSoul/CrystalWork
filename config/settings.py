"""
Django settings for config project.
"""

from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import os

load_dotenv()


# ============================================================
# BASE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# RESTFramework
# ============================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}


# ============================================================
# SECURITY
# ============================================================

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-local-development-key"
)

DEBUG = os.environ.get("DEBUG", "True").lower() == "true"


# ============================================================
# VERCEL
# ============================================================

VERCEL = os.environ.get("VERCEL") == "1"

VERCEL_URL = os.environ.get("VERCEL_URL", "")
VERCEL_PROJECT_PRODUCTION_URL = os.environ.get(
    "VERCEL_PROJECT_PRODUCTION_URL",
    ""
)


# ============================================================
# ALLOWED HOSTS
# ============================================================

# Hosts básicos para desarrollo local
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "*"
]


# Hosts adicionales definidos manualmente desde Vercel
extra_hosts = os.environ.get("ALLOWED_HOSTS", "")

if extra_hosts:
    ALLOWED_HOSTS.extend(
        host.strip()
        for host in extra_hosts.split(",")
        if host.strip()
    )


# Vercel proporciona VERCEL_URL con el hostname del deployment actual.
if VERCEL_URL:
    ALLOWED_HOSTS.append(VERCEL_URL)


# Dominio de producción del proyecto, si está disponible.
if VERCEL_PROJECT_PRODUCTION_URL:
    ALLOWED_HOSTS.append(VERCEL_PROJECT_PRODUCTION_URL)


# ============================================================
# CSRF
# ============================================================

CSRF_TRUSTED_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
]


extra_csrf_origins = os.environ.get(
    "CSRF_TRUSTED_ORIGINS",
    ""
)

if extra_csrf_origins:
    CSRF_TRUSTED_ORIGINS.extend(
        origin.strip()
        for origin in extra_csrf_origins.split(",")
        if origin.strip()
    )


# Vercel Preview / Production
if VERCEL_URL:
    CSRF_TRUSTED_ORIGINS.append(
        f"https://{VERCEL_URL}"
    )

if VERCEL_PROJECT_PRODUCTION_URL:
    CSRF_TRUSTED_ORIGINS.append(
        f"https://{VERCEL_PROJECT_PRODUCTION_URL}"
    )


# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "import_export",
    "simple_history",

    # Custom
    "alerts",       #Aplicación para alertas y notificaciones
    "analytics",    #Aplicación para analítica y métricas (BI)
    "core",         #Aplicación principal, contiene la cotizacion, proyectos, clientes, ventanas, materiales, etc.
    "projects",     #Aplicación que contiene el modulo temporal de hoja de corte
    "users",        #Aplicacion para control de usuarios, empresas, empleados y permisos

    "api",
    "rest_framework",
    "corsheaders",
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
]


# ============================================================
# URLS
# ============================================================

ROOT_URLCONF = "config.urls"


# ============================================================
# TEMPLATES
# ============================================================

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


# ============================================================
# WSGI
# ============================================================

WSGI_APPLICATION = "config.wsgi.application"


# ============================================================
# DATABASE
# ============================================================

# Por defecto usamos SQLite (desarrollo). Si se definen las variables
# POSTGRES_* en el entorno, la aplicacion cambia a PostgreSQL sin tocar
# codigo. SQLite NO es apto para despliegues serverless (p. ej. Vercel).

if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ============================================================
# AUTH
# ============================================================

AUTH_USER_MODEL = "users.Usuario"


# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = "es-es"

TIME_ZONE = "America/Santiago"

USE_I18N = True

USE_TZ = True


# ============================================================
# STATIC FILES
# ============================================================

STATIC_URL = "static/"


# ============================================================
# EMAIL
# ============================================================

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

# ============================================================
# CORS
# ============================================================

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True