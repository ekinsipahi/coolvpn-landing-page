# core/settings.py
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


# ---- .env yükleyici (bağımlılıksız): BASE_DIR/.env varsa okur,
#      mevcut ortam değişkenlerini ezmez. Hassas değerlerin TEK kaynağı .env'dir.
def _load_env(path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


_load_env(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

# ---- HTTP cron tetikleyici (cron-job.org icin)
CRON_SECRET = os.environ.get("CRON_SECRET", "").strip()

# ---- Analytics
GA_MEASUREMENT_ID = os.environ.get("GA_MEASUREMENT_ID", "")

# ---- Site kimliği
SITE_NAME = "VPNsterr"
SUPPORT_EMAIL = "support@vpnsterr.com"

# ---- Tuzel kisilik bilgileri (Eesti ariregister ozeti, 04.09.2026)
# Tek kaynak: footer, Organization JSON-LD ve hukuki sayfalar buradan besleniyor.
# BILEREK BURADA OLMAYANLAR:
#   * juhatuse liikme isikukood (kisisel kimlik no) -- kimlik hirsizligi
#     malzemesi, hicbir yerde yayinlanmaz;
#   * kurucunun sahsi gmail adresi -- yazisma support@ uzerinden yurur.
COMPANY_LEGAL_NAME = "Sterr Technologies OÜ"
COMPANY_LEGAL_FORM = "Private limited company (osaühing)"
COMPANY_REG_CODE = "17591465"
COMPANY_REGISTRY_NAME = "Estonian Business Register"
COMPANY_REGISTRY_URL = "https://ariregister.rik.ee/eng/company/17591465"
COMPANY_REGISTERED_ON = "4 September 2026"
COMPANY_DUNS = "988022933"
COMPANY_ADDRESS_STREET = "Tornimäe tn 5"
COMPANY_ADDRESS_LOCALITY = "Tallinn"
COMPANY_ADDRESS_REGION = "Harju maakond"
COMPANY_ADDRESS_POSTAL = "10145"
COMPANY_ADDRESS_COUNTRY = "Estonia"
COMPANY_ADDRESS_LINE = ("Tornimäe tn 5, Kesklinna linnaosa, "
                        "10145 Tallinn, Estonia")
# Yonetim kurulu uyesi: ariregistrde herkese acik. Kaldirmak istersen bosalt.
COMPANY_DIRECTOR = "Ekin Ahmed Sipahi"
# Chrome Web Store — yayında (2026-09-10). Env ile override edilebilir.
CHROME_STORE_URL = os.environ.get(
    "CHROME_STORE_URL",
    "https://chromewebstore.google.com/detail/free-vpn-for-chrome-vpn-p/llmhkchghidfojlbdelkebgohjfjijmg",
)

# ---- Sentry (hata + performans izleme)
# DSN'i .env'e koy: SENTRY_DSN=https://...@...ingest.de.sentry.io/...
# DSN boşsa Sentry hiç başlatılmaz — dev'de gürültü yapmaz, deploy'u bozmaz.
# NOT: Sentry "auth token" ile DSN AYNI ŞEY DEĞİL; auth token release/sourcemap
# yüklemek için sentry-cli'nin kullandığı şey, uygulamanın ihtiyacı olan DSN'dir.
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
SENTRY_ENVIRONMENT = os.environ.get("SENTRY_ENVIRONMENT", "production" if not DEBUG else "development")
SENTRY_TRACES_SAMPLE_RATE = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        from core.sentry_scrub import scrub as _sentry_scrub

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            integrations=[
                DjangoIntegration(),
                # WARNING+ olay olarak gider; INFO'lar breadcrumb kalır.
                LoggingIntegration(level=None, event_level="WARNING"),
            ],
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            # PII gönderme: kullanıcı e-postası/IP'si Sentry'ye taşınmasın.
            # "Zero logs" sözü veren bir üründe bu pazarlama değil, zorunluluk.
            send_default_pii=False,
            max_request_body_size="never",
            # Sentry'nin varsayilan filtresi Authorization/Cookie basliklarini
            # temizler ama QUERY STRING'e dokunmaz; bizde sir orada dolasiyor
            # (/api/cron/reconcile/?key=...). Ayrintili gerekce: core/sentry_scrub.py
            before_send=_sentry_scrub,
            before_send_transaction=_sentry_scrub,
        )
    except Exception:  # noqa: BLE001 - izleme aracı uygulamayı düşüremez
        pass

# ---- 3D Secure zorunluluğu
# "challenge": ihraççı destekliyorsa HER ödemede doğrulama istenir. Kart
# deneyen biri bankanın doğrulamasını geçemez ve sahtecilik sorumluluğu
# ihraççıya geçer. Not: her kart 3DS desteklemez (bazı ABD kartları);
# desteklemeyende Stripe sürtünmesiz akışa düşer — bu bizim elimizde değil.
# Dönüşüm belirgin düşerse "automatic" yaparak geri alabilirsin.
STRIPE_3DS_MODE = os.environ.get("STRIPE_3DS_MODE", "challenge").strip() or "challenge"

# ---- Cloudflare Turnstile (hesap açmada bot freni)
# Anahtarlar: Cloudflare Dashboard > Turnstile > Add site.
# Boşsa doğrulama KAPALI olur (dev'de rahat çalışılsın diye); canlıda
# ikisini de doldur, yoksa kayıt formu korumasız kalır.
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "").strip()
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "").strip()

# ---- Site URL (dev/prod’a göre ayarla)
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000")

# Domain taşıma: eski hostlar 301 ile buraya yönlenir
CANONICAL_HOST = os.environ.get("CANONICAL_HOST", "vpnsterr.com")
OLD_HOSTS = [h for h in os.environ.get("OLD_HOSTS", "coolvpn.app,www.coolvpn.app,www.vpnsterr.com").split(",") if h.strip()]

# Eklenti/havuz köprüsü: siteyi token-imzalayan otorite yapan paylaşılan sır.
# Havuz (pool.vpnsterr.com) AYNI değeri kullanıp sadece doğrular.
# .strip() ve tırnak soyma ŞART: havuzun env.py'ı bunu yapıyor; site ham
# okusaydı, panele yanlışlıkla tırnaklı/sonunda boşluklu girilen bir değer
# site tarafında imzaya dahil olur, havuzda temizlenir, imza tutmaz ve HER
# premium cihaz sessizce free'ye düşerdi. İki taraf artık aynı temizliği yapar.
EXTENSION_SHARED_SECRET = os.environ.get("EXTENSION_SHARED_SECRET", "").strip().strip('"').strip("'").strip()
EXTENSION_TOKEN_TTL_SECONDS = int(os.environ.get("EXTENSION_TOKEN_TTL_SECONDS", "3600"))  # prod .env'de: https://vpnsterr.com

# ------------ Apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",             # <-- sitemap.xml
    "django.contrib.sites",                # <-- GEREKLİ
    "allauth",                             # <-- GEREKLİ
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",

    "landing",
    "blog",
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
# allauth'un kendi kayit sayfasi kapali: siteden linki yok, gercek akis
# /auth/email-upsert-login/ ve orada Turnstile var. Bkz. account_adapter.py
ACCOUNT_ADAPTER = "landing.account_adapter.ClosedSignupAdapter"
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "optional"   # prod’da 'mandatory' yap
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 300
ACCOUNT_PASSWORD_MIN_LENGTH = 5

# ------------ Allauth / Google (hardcode)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# Dev’de http çalışıyorsun:
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"

# ------------ Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.DomainRedirectMiddleware",  # coolvpn.app -> vpnsterr.com 301
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
    # Şimdilik sadece İngilizce. Diğer dilleri açmak için bu listeyi geri genişlet:
    # ("tr", "Türkçe"), ("ar", "العربية"), ("fa", "فارسی"), ("ru", "Русский"),
    # ("zh-hans", "简体中文"), ("hi", "हिन्दी"), ("ur", "اردو"), ("id", "Bahasa Indonesia"),
    # ("ms", "Bahasa Melayu"), ("de", "Deutsch"), ("fr", "Français"), ("es", "Español"),
    # ("it", "Italiano"), ("nl", "Nederlands"), ("pl", "Polski"), ("uk", "Українська"),
    # ("he", "עברית"), ("ro", "Română"), ("az", "Azərbaycan dili"),
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
    "default": {
        "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.environ.get("DB_NAME", "postgres"),
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", ""),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}


# ------------ E-posta (şifre sıfırlama vb.) — dev: console, prod: SMTP (.env)
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "VPNsterr <support@vpnsterr.com>")

# ------------ Resend — işlem/pazarlama mailleri (welcome, premium aktif, ticket)
# Boşsa landing.helpers.mailer Django EMAIL_BACKEND'e düşer (dev'de console).
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
NOREPLY_EMAIL = os.environ.get("NOREPLY_EMAIL", "VPNsterr <noreply@vpnsterr.com>").strip()
# Ticket/escalation bildirimlerinin yönlendiği operatör adresi.
SUPPORT_FORWARD_EMAIL = os.environ.get("SUPPORT_FORWARD_EMAIL", "").strip()

# ------------ AI asistan (köşedeki chatbox) — Claude
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
ASSISTANT_MODEL = os.environ.get("ASSISTANT_MODEL", "claude-haiku-4-5-20251001").strip()

# ------------ Static
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# Stripe — anahtarlar .env'den gelir
# ============================================================
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "") or os.environ.get("STRIPE_PUBLISH_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# ============================================================
# NOWPayments (TRX sabit)
# ============================================================
NOWPAYMENTS = {
    "BASE_URL": "https://api.nowpayments.io/v1",
    "PAY_CURRENCY": "TRX",  # ödemeyi TRON (TRX) ile topla
    "SUCCESS_URL": f"{SITE_URL}/payment/success/",
    "CANCEL_URL":  f"{SITE_URL}/payment/cancel/",
    "IPN_URL":     f"{SITE_URL}/api/payment/nowpayments/ipn/",
    # Güvenlik & auth — .env'den gelir
    "API_KEY":    os.environ.get("NOWPAYMENTS_API_KEY", ""),
    "IPN_SECRET": os.environ.get("NOWPAYMENTS_IPN_SECRET", ""),
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
