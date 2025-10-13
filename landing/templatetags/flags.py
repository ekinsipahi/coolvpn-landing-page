# yourapp/templatetags/flags.py
from django import template

register = template.Library()

# Tam/özel eşleşmeler (bölgeseller dahil)
FULL_FLAG_MAP = {
    # English varyantları
    "en": "🇺🇸",       # istersen "🇬🇧" yapabilirsin
    "en-us": "🇺🇸",
    "en-gb": "🇬🇧",

    # Chinese varyantları
    "zh": "🇨🇳",
    "zh-cn": "🇨🇳",
    "zh-hans": "🇨🇳",  # simplified
    "zh-tw": "🇹🇼",
    "zh-hk": "🇭🇰",
    "zh-hant": "🇹🇼",  # traditional -> TW (istersen HK yap)

    # Portuguese varyantları (bonus)
    "pt": "🇵🇹",
    "pt-pt": "🇵🇹",
    "pt-br": "🇧🇷",

    # Geri kalanlar (temel)
    "tr": "🇹🇷",
    "ar": "🇸🇦",
    "fa": "🇮🇷",
    "ru": "🇷🇺",
    "hi": "🇮🇳",
    "ur": "🇵🇰",
    "id": "🇮🇩",
    "ms": "🇲🇾",
    "de": "🇩🇪",
    "fr": "🇫🇷",
    "es": "🇪🇸",
    "it": "🇮🇹",
    "nl": "🇳🇱",
    "pl": "🇵🇱",
    "uk": "🇺🇦",
    "he": "🇮🇱",
    "ro": "🇷🇴",
    "az": "🇦🇿",
}

# Eski/alternatif ISO kodlarını normalize etmek için alias’lar
ALIASES = {
    "iw": "he",   # eski Hebrew
    "in": "id",   # eski Indonesian
    "ua": "uk",   # gayriresmi Ukraine
}

@register.filter
def flag_emoji(lang_code: str) -> str:
    """
    lang_code (örn: 'en', 'en-GB', 'zh_Hans', 'pt-BR') -> bayrak emoji
    """
    if not lang_code:
        return "🌐"

    code = str(lang_code).strip().lower().replace("_", "-")

    # alias düzelt
    code = ALIASES.get(code, code)

    # 1) Tam eşleşme
    if code in FULL_FLAG_MAP:
        return FULL_FLAG_MAP[code]

    # 2) Kök dile düş (en-GB -> en)
    base = code.split("-")[0]
    base = ALIASES.get(base, base)
    if base in FULL_FLAG_MAP:
        return FULL_FLAG_MAP[base]

    # 3) Bulunamazsa globe
    return "🌐"
