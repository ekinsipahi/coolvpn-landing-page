# core/context_processors.py
from django.conf import settings
from django.urls import translate_url
from django.utils.translation import get_language
import json

def seo(request):
    """
    - canonical_url: querystringsiz absolute URL
    - hreflang_urls: (lang_code, translated_abs_url) listesi
    - org_schema_json: site geneli Organization JSON-LD
    """
    try:
        abs_url = request.build_absolute_uri(request.path)
    except Exception:
        abs_url = ""

    hreflang_urls = []
    for code, _ in getattr(settings, "LANGUAGES", [("en", "English")]):
        try:
            href = translate_url(abs_url, code)
            hreflang_urls.append((code, href))
        except Exception:
            continue

    # OG locale basit eşlem (gerekirse genişlet)
    lang = get_language() or "en"
    og_locale_map = {
        "en": "en_US", "tr": "tr_TR", "ar": "ar_SA", "fa": "fa_IR",
        "ru": "ru_RU", "de": "de_DE", "fr": "fr_FR", "es": "es_ES",
        "it": "it_IT", "nl": "nl_NL", "pl": "pl_PL", "uk": "uk_UA",
        "he": "he_IL", "ro": "ro_RO", "az": "az_AZ", "id": "id_ID",
        "ms": "ms_MY", "hi": "hi_IN", "ur": "ur_PK", "zh-hans": "zh_CN",
    }
    og_locale = og_locale_map.get(lang.split("-")[0], "en_US")

    # Tuzel kisilik: footer ve JSON-LD ayni kaynaktan beslensin ki biri
    # guncellenip digeri eskide kalmasin (hukuki metinde tehlikeli olurdu).
    company = {
        "legal_name": getattr(settings, "COMPANY_LEGAL_NAME", ""),
        "legal_form": getattr(settings, "COMPANY_LEGAL_FORM", ""),
        "reg_code": getattr(settings, "COMPANY_REG_CODE", ""),
        "registry_name": getattr(settings, "COMPANY_REGISTRY_NAME", ""),
        "registry_url": getattr(settings, "COMPANY_REGISTRY_URL", ""),
        "registered_on": getattr(settings, "COMPANY_REGISTERED_ON", ""),
        "duns": getattr(settings, "COMPANY_DUNS", ""),
        "address_line": getattr(settings, "COMPANY_ADDRESS_LINE", ""),
        "director": getattr(settings, "COMPANY_DIRECTOR", ""),
        "support_email": getattr(settings, "SUPPORT_EMAIL", "support@vpnsterr.com"),
    }

    # ---- Site geneli JSON-LD ----
    # TEK @id, TEK kaynak: sayfa şablonları publisher/provider alanında bu
    # düğüme {"@id": ...} ile bağlanıyor. Önceden her sayfa kendi
    # Organization'ını gömüyordu ve içlerinde tüzel ad "Sterr Technologies"
    # olarak kalmıştı — sicildeki ad "Sterr Technologies OÜ". Arama motoru
    # için bunlar AYRI iki kuruluş demek; footer'daki kimlikle de çelişiyordu.
    #
    # Taban adres canonical host'tan: SITE_URL dev'de 127.0.0.1 olduğu için
    # @id'ler ortama göre kayardı, o da düğümleri birbirinden koparırdı.
    site_base = f"https://{getattr(settings, 'CANONICAL_HOST', 'vpnsterr.com')}"
    org_id = f"{site_base}/#org"

    org_schema = {
        "@type": "Organization",
        "@id": org_id,
        "name": getattr(settings, "SITE_NAME", "VPNsterr"),
        "legalName": company["legal_name"] or "Sterr Technologies OÜ",
        "url": site_base,
        "email": company["support_email"],
        "foundingDate": "2026-09-04",
        # Dogrulanabilir kimlik: arama motorlari ve "bu gercek bir sirket mi"
        # diye bakan kullanici icin en agirlikli sinyal bunlar.
        "address": {
            "@type": "PostalAddress",
            "streetAddress": getattr(settings, "COMPANY_ADDRESS_STREET", ""),
            "addressLocality": getattr(settings, "COMPANY_ADDRESS_LOCALITY", ""),
            "addressRegion": getattr(settings, "COMPANY_ADDRESS_REGION", ""),
            "postalCode": getattr(settings, "COMPANY_ADDRESS_POSTAL", ""),
            "addressCountry": "EE",
        },
        "identifier": [
            {"@type": "PropertyValue", "name": "Estonian Business Register code",
             "value": company["reg_code"]},
            {"@type": "PropertyValue", "name": "D-U-N-S", "value": company["duns"]},
        ],
        "logo": {
            "@type": "ImageObject",
            "url": f"{site_base}/static/img/VPNSTERR-LOGO.png",
        },
        "contactPoint": {
            "@type": "ContactPoint",
            "contactType": "customer support",
            "email": getattr(settings, "SUPPORT_EMAIL", "support@vpnsterr.com"),
            "availableLanguage": ["en", "tr"],
        },
        "sameAs": getattr(settings, "SITE_SAMEAS", [
            "https://x.com/vpnsterr",
            "https://instagram.com/vpnsterr",
            "https://www.tiktok.com/@vpnsterr",
        ]) + ([company["registry_url"]] if company["registry_url"] else []),
    }
    # WebSite düğümü: siteyi kuruluşa bağlar. Bu olmadan arama motoru
    # "vpnsterr.com" ile "Sterr Technologies OÜ"yü aynı varlık saymak
    # zorunda değil.
    website_schema = {
        "@type": "WebSite",
        "@id": f"{site_base}/#website",
        "url": site_base,
        "name": getattr(settings, "SITE_NAME", "VPNsterr"),
        "publisher": {"@id": org_id},
        "inLanguage": "en",
    }
    org_schema_json = json.dumps(
        {"@context": "https://schema.org", "@graph": [org_schema, website_schema]},
        ensure_ascii=False)

    return {
        "GA_MEASUREMENT_ID": getattr(settings, "GA_MEASUREMENT_ID", ""),
        "site_name": getattr(settings, "SITE_NAME", "VPNsterr"),
        "default_description": getattr(
            settings, "DEFAULT_DESCRIPTION",
            "Privacy-first VPN. Strict no-logs. Unlimited bandwidth on every device."
        ),
        "canonical_url": abs_url,
        "hreflang_urls": hreflang_urls,
        "og_locale": og_locale,
        "org_schema_json": org_schema_json,
        "company": company,
        # Sayfa şablonları publisher/provider'ı buna bağlasın diye.
        "org_id": org_id,
        # Turnstile site anahtarı: boşsa şablonlar widget'ı hiç basmaz,
        # doğrulama da sunucuda kapalı olur (ikisi aynı anahtara bakar).
        "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", ""),
        # Uzantı kurulum CTA'ları her sayfada var; view'dan view'a
        # taşımak yerine global veriyoruz (dashboard build_ui_context kullanmıyor).
        "chrome_store_url": getattr(settings, "CHROME_STORE_URL", ""),
    }
