"""
Django settings for config project.
"""

from pathlib import Path
from datetime import timedelta
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
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
        "users.auth.JWTEmpresaActivaAuthentication",
    ),
    # Por defecto solo usuarios de una empresa (el administrador del sistema
    # no ve datos operativos). Ver core/permissions.py.
    "DEFAULT_PERMISSION_CLASSES": [
        "core.permissions.EsUsuarioDeEmpresa",
    ],
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    # Registra el "último ingreso" del usuario al iniciar sesión (por defecto
    # SimpleJWT no lo actualiza).
    "UPDATE_LAST_LOGIN": True,
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
# ALLOWED HOSTS
# ============================================================

# Desarrollo local. En producción se agregan por la variable de entorno
# ALLOWED_HOSTS (hosts separados por coma).
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]

extra_hosts = os.environ.get("ALLOWED_HOSTS", "")

if extra_hosts:
    ALLOWED_HOSTS.extend(
        host.strip()
        for host in extra_hosts.split(",")
        if host.strip()
    )


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
    # Zona horaria del navegador para los textos con hora (core/zona.py).
    "core.zona.ZonaClienteMiddleware",
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

# SQLite queda como opción local cuando no se configura PostgreSQL. Si se
# configura cualquier variable de PostgreSQL, exigimos el resto para evitar
# que una configuración incompleta use SQLite sin avisar. En producción se
# recomienda PostgreSQL (SQLite no es apto para despliegues serverless ni con
# múltiples procesos).
postgres_required = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
)
postgres_configured = any(name in os.environ for name in postgres_required)

if postgres_configured:
    missing_postgres_settings = [
        name for name in postgres_required if not os.environ.get(name)
    ]
    if missing_postgres_settings:
        raise ImproperlyConfigured(
            "Faltan variables para conectar a PostgreSQL: "
            + ", ".join(missing_postgres_settings)
        )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ["POSTGRES_USER"],
            "PASSWORD": os.environ["POSTGRES_PASSWORD"],
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "connect_timeout": int(
                    os.environ.get("POSTGRES_CONNECT_TIMEOUT", "10")
                ),
                "sslmode": os.environ.get("POSTGRES_SSLMODE", "require"),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            # SQLite admite un solo escritor a la vez. Como el front guarda
            # varias filas en paralelo (edicion en bloque) y runserver es
            # multihilo, sin esto la segunda escritura falla al instante con
            # "database is locked". WAL deja leer mientras alguien escribe;
            # busy_timeout hace que el escritor que llega segundo ESPERE (hasta
            # 20 s) en vez de fallar; transaction_mode=IMMEDIATE toma el lock de
            # escritura al abrir la transaccion, evitando el bloqueo al pasar de
            # lectura a escritura. (Django 5.1+.)
            "OPTIONS": {
                "timeout": 20,
                "transaction_mode": "IMMEDIATE",
                "init_command": (
                    "PRAGMA journal_mode=WAL;"
                    "PRAGMA synchronous=NORMAL;"
                    "PRAGMA busy_timeout=20000;"
                ),
            },
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
# CORS
# ============================================================

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
# Cabecera con la zona horaria del navegador (core/zona.py).
CORS_ALLOW_HEADERS = (*default_headers, "x-zona-horaria")