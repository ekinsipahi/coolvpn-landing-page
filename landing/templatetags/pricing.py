# landing/pricing.py
import json
from django.urls import reverse
from django.utils.translation import gettext as _

PRICING_BY_COUNTRY = {
    # Tier A
    "US": {"currency": "USD", "monthly": 4.99,  "annual": 39.99,  "semiannual": 25.80},
    "GB": {"currency": "GBP", "monthly": 3.99,  "annual": 31.99,  "semiannual": 20.63},
    "DE": {"currency": "EUR", "monthly": 4.59,  "annual": 36.99,  "semiannual": 23.75},
    "FR": {"currency": "EUR", "monthly": 4.59,  "annual": 36.99,  "semiannual": 23.75},
    "IT": {"currency": "EUR", "monthly": 4.59,  "annual": 36.99,  "semiannual": 23.75},
    "NL": {"currency": "EUR", "monthly": 4.59,  "annual": 36.99,  "semiannual": 23.75},
    "ES": {"currency": "EUR", "monthly": 4.59,  "annual": 36.99,  "semiannual": 23.75},
    "IL": {"currency": "ILS", "monthly": 18.49, "annual": 144.99, "semiannual": 95.26},
    "SA": {"currency": "SAR", "monthly": 16.99, "annual": 134.99, "semiannual": 87.71},
    "AE": {"currency": "AED", "monthly": 16.99, "annual": 134.99, "semiannual": 87.71},

    # Türkiye
    "TR": {"currency": "TRY", "monthly": 99.00, "annual": 990.00, "semiannual": 531.43},

    # Tier B
    "RU": {"currency": "RUB", "monthly": 239,   "annual": 1899,   "semiannual": 1233.85},
    "CN": {"currency": "CNY", "monthly": 21.90, "annual": 169,    "semiannual": 112.56},
    "MY": {"currency": "MYR", "monthly": 11.90, "annual": 89.00,  "semiannual": 60.88},
    "PL": {"currency": "PLN", "monthly": 12.99, "annual": 99,     "semiannual": 66.64},
    "RO": {"currency": "RON", "monthly": 11.99, "annual": 89.99,  "semiannual": 61.37},
    "AZ": {"currency": "AZN", "monthly": 3.49,  "annual": 27.99,  "semiannual": 18.04},

    # Tier C
    "IN": {"currency": "INR", "monthly": 129,   "annual": 999,    "semiannual": 663.37},
    "PK": {"currency": "PKR", "monthly": 359,   "annual": 2799,   "semiannual": 1848.01},
    "ID": {"currency": "IDR", "monthly": 22900, "annual": 179000, "semiannual": 117927},
    "EG": {"currency": "EGP", "monthly": 65,    "annual": 499,    "semiannual": 333.82},
    "UA": {"currency": "UAH", "monthly": 59,    "annual": 459,    "semiannual": 303.61},
    "IR": {"currency": "IRR", "monthly": 499000,"annual": 3990000,"semiannual": 2578632},
    "MX": {"currency": "MXN", "monthly": 44.99, "annual": 349,    "semiannual": 231.42},
}

DEFAULT_COUNTRY = "US"

LANG_TO_DEFAULT_COUNTRY = {
    "en": "US", "tr": "TR", "ar": "SA", "fa": "IR", "ru": "RU", "zh-hans": "CN",
    "hi": "IN", "ur": "PK", "id": "ID", "ms": "MY", "de": "DE", "fr": "FR",
    "es": "ES", "it": "IT", "nl": "NL", "pl": "PL", "uk": "UA", "he": "IL",
    "ro": "RO", "az": "AZ",
}

CURRENCY_SYMBOLS = {
    "USD":"$", "EUR":"€", "GBP":"£", "TRY":"₺", "ILS":"₪", "SAR":"﷼", "AED":"د.إ",
    "RUB":"₽", "CNY":"¥", "INR":"₹", "PKR":"₨", "IDR":"Rp", "MYR":"RM", "PLN":"zł",
    "UAH":"₴", "RON":"lei", "AZN":"₼", "EGP":"E£", "MXN":"$"
}

def currency_symbol(code: str) -> str:
    return CURRENCY_SYMBOLS.get(code, code)

def detect_country(request) -> str:
    cf = request.META.get("HTTP_CF_IPCOUNTRY")
    if cf and len(cf) == 2:
        return cf.upper()

    al = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    for part in al.split(","):
        tag = part.strip().split(";")[0]
        if "-" in tag:
            _, cc = tag.split("-", 1)
            if len(cc) == 2:
                return cc.upper()

    lang = (getattr(request, "LANGUAGE_CODE", "") or "").lower()
    if lang in LANG_TO_DEFAULT_COUNTRY:
        return LANG_TO_DEFAULT_COUNTRY[lang]
    return DEFAULT_COUNTRY

def _abs_localized_url(request, viewname: str) -> str:
    path = reverse(viewname)
    return request.build_absolute_uri(path)

def build_all_offers_json(pricing_by_country: dict, request) -> str:
    """
    Product.offers için TÜM ülkeler (monthly + 6-month + annual)
    """
    offers = []
    for cc, p in pricing_by_country.items():
        for plan_name, key in (
            (_("Monthly Plan"), "monthly"),
            (_("6-Month Plan"), "semiannual"),
            (_("Annual Plan"), "annual"),
        ):
            price_val = p[key]
            price_str = f"{price_val:.2f}" if isinstance(price_val, float) else f"{price_val}"
            offers.append({
                "@type": "Offer",
                "name": plan_name,
                "priceCurrency": p["currency"],
                "price": price_str,
                "availability": "https://schema.org/InStock",
                "eligibleRegion": cc,
                "url": _abs_localized_url(request, "pricing"),
            })
    return json.dumps(offers, ensure_ascii=False)

def get_pricing_for_request(request):
    """
    View/context için tek noktadan fiyat ver.
    """
    cc = detect_country(request)
    data = PRICING_BY_COUNTRY.get(cc, PRICING_BY_COUNTRY[DEFAULT_COUNTRY])
    return {
        "country_code": cc,
        "currency_code": data["currency"],
        "currency_symbol": currency_symbol(data["currency"]),
        "monthly": data["monthly"],
        "semiannual": data["semiannual"],
        "annual": data["annual"],
    }


def _abs_localized_url(request, viewname: str) -> str:
    path = reverse(viewname)
    return request.build_absolute_uri(path)

def build_all_offers_json(pricing_by_country: dict, request) -> str:
    """
    Product.offers için TÜM ülkeler (monthly + 6-month + annual)
    Her offer içine minimal shippingDetails + hasMerchantReturnPolicy eklenir.
    """
    offers = []
    for cc, p in pricing_by_country.items():
        for plan_name, key in (
            ("Monthly Plan", "monthly"),
            ("6-Month Plan", "semiannual"),
            ("Annual Plan", "annual"),
        ):
            price_val = p[key]
            price_str = f"{price_val:.2f}" if isinstance(price_val, float) else f"{price_val}"
            # basit shippingDetails (örnek) -- ülke bazlı olabiliyor
            shipping = {
                "@type": "OfferShippingDetails",
                "shippingDestination": {
                    "@type": "DefinedRegion",
                    "addressCountry": cc
                },
                "shippingRate": {
                    "@type": "MonetaryAmount",
                    "value": "0",
                    "currency": p["currency"]
                }
            }
            merchant_return = {
                "@type": "MerchantReturnPolicy",
                # Kısa/manifest bir kategori koyuyoruz; gerekirse detaylandır.
                "returnPolicyCategory": "https://schema.org/MerchantReturnUnspecified"
            }

            offers.append({
                "@type": "Offer",
                "name": plan_name,
                "priceCurrency": p["currency"],
                "price": price_str,
                "availability": "https://schema.org/InStock",
                "eligibleRegion": cc,
                "url": _abs_localized_url(request, "pricing"),
                "shippingDetails": shipping,
                "hasMerchantReturnPolicy": merchant_return
            })
    return json.dumps(offers, ensure_ascii=False)
