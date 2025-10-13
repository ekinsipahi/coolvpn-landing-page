# core/settings.py
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-og-03q*s7tt+!f@*4f%!-th8&1#prrb3$ad*9vkc7_+an#j&j*"
DEBUG = True
ALLOWED_HOSTS = ["*"]

# ---- Site URL (dev/prod’a göre ayarla)
SITE_URL = "http://127.0.0.1:8000"  # prod'da: "https://coolvpn.yourdomain.com"

# ------------ Apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",                # <-- GEREKLİ
    "allauth",                             # <-- GEREKLİ
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",

    "landing",
]

SITE_ID = 1  # <-- Sites framework

# ------------ Auth backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"   # istersen farklı bir sayfa
LOGOUT_REDIRECT_URL = "home"   # varsa home route’unun adı

ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# ------------ Account (e-posta odaklı)
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "optional"   # prod’da 'mandatory' yap
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 300
ACCOUNT_PASSWORD_MIN_LENGTH = 5

# ------------ Allauth / Google (hardcode)
GOOGLE_CLIENT_ID = "990410161189-3aceuojrmhnc73h85f8porlmmj1ab3ia.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"

# Dev’de http çalışıyorsun:
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"

# ------------ Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static dev/prod rahatlığı
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # <-- GEREKLİ
    "core.middleware.CoopAllowPopupsMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

SECURE_CROSS_ORIGIN_OPENER_POLICY = None  # global COOP yazmasın

# Dev’de bazı POST’lar için faydalı:
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

# ------------ i18n
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("tr", "Türkçe"),
    ("ar", "العربية"),
    ("fa", "فارسی"),
    ("ru", "Русский"),
    ("zh-hans", "简体中文"),
    ("hi", "हिन्दी"),
    ("ur", "اردو"),
    ("id", "Bahasa Indonesia"),
    ("ms", "Bahasa Melayu"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("nl", "Nederlands"),
    ("pl", "Polski"),
    ("uk", "Українська"),
    ("he", "עברית"),
    ("ro", "Română"),
    ("az", "Azərbaycan dili"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_NAME = "django_language"
LANGUAGE_COOKIE_SAMESITE = "Lax"

# ------------ Templates
ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",   # <-- GEREKLİ (allauth)
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.seo",
            ],
            'libraries': {
                'flags': 'landing.templatetags.flags',
            }
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# ------------ DB
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': 'postgres.hsgwbsdhtxbhinulzfbg',
        'PASSWORD': '27J43*12_!Z12a',
        'HOST': 'aws-1-us-east-1.pooler.supabase.com',
        'PORT': '5432',  # DOĞRUDAN bağlantı
    }
}


# ------------ Static
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# NOWPayments (TRX sabit)
# ============================================================
NOWPAYMENTS = {
    "BASE_URL": "https://api.nowpayments.io/v1",
    "PAY_CURRENCY": "TRX",  # ödemeyi TRON (TRX) ile topla
    "SUCCESS_URL": f"{SITE_URL}/payment/success/",
    "CANCEL_URL":  f"{SITE_URL}/payment/cancel/",
    "IPN_URL":     f"{SITE_URL}/api/payment/nowpayments/ipn/",
    # Güvenlik & auth (KULLANICI VERDİĞİN)
    "API_KEY":    "9D9WWG0-YWC4QMJ-G6DQKZ9-AGQBFDZ",
    "IPN_SECRET": "DM1GV5TdP0uhre2IVmEAoTyatw/4/1jv",
    # Ücreti kim öder? True → müşteri (NOWPayments fee)
    "FEE_PAID_BY_USER": True,
}

# Kısa erişim için düz değişkenler (opsiyonel)
NOWPAYMENTS_API_KEY = NOWPAYMENTS["API_KEY"]
NOWPAYMENTS_IPN_SECRET = NOWPAYMENTS["IPN_SECRET"]
NOWPAYMENTS_BASE_URL = NOWPAYMENTS["BASE_URL"]
NOWPAYMENTS_PAY_CURRENCY = NOWPAYMENTS["PAY_CURRENCY"]
NOWPAYMENTS_SUCCESS_URL = NOWPAYMENTS["SUCCESS_URL"]
NOWPAYMENTS_CANCEL_URL = NOWPAYMENTS["CANCEL_URL"]
NOWPAYMENTS_IPN_URL = NOWPAYMENTS["IPN_URL"]
NOWPAYMENTS_FEE_PAID_BY_USER = NOWPAYMENTS["FEE_PAID_BY_USER"]
ORDER_PENDING_TTL_HOURS = 5
