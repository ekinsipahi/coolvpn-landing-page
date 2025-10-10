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

    # Organization JSON-LD (global)
    org_schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": getattr(settings, "SITE_NAME", "CoolVPN"),
        "url": getattr(settings, "SITE_URL", ""),
        "logo": getattr(settings, "SITE_LOGO_URL", ""),
        "sameAs": getattr(settings, "SITE_SAMEAS", []),
    }
    org_schema_json = json.dumps(org_schema, ensure_ascii=False)

    return {
        "site_name": getattr(settings, "SITE_NAME", "CoolVPN"),
        "default_description": getattr(
            settings, "DEFAULT_DESCRIPTION",
            "Privacy-first VPN. Audited no-logs. Obfuscation for restricted networks."
        ),
        "canonical_url": abs_url,
        "hreflang_urls": hreflang_urls,
        "og_locale": og_locale,
        "org_schema_json": org_schema_json,
    }
