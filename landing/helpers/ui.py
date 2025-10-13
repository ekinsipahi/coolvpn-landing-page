from django.utils.translation import gettext as _
from landing.templatetags.pricing import (
    PRICING_BY_COUNTRY, detect_country, currency_symbol, build_all_offers_json
)
from .money import fmt_two
from typing import Tuple, Dict

# -----------------------------
# UI helpers
# -----------------------------
def build_ui_context(request):
    user_cc = detect_country(request)
    region = PRICING_BY_COUNTRY.get(user_cc, PRICING_BY_COUNTRY["US"])
    ui_currency = region["currency"]
    ui_symbol = currency_symbol(ui_currency)
    ctx_ui = {
        "ui_country": user_cc,
        "ui_currency": ui_currency,
        "ui_currency_symbol": ui_symbol,
        "ui_monthly":    f"{region['monthly']:.2f}" if isinstance(region["monthly"], float) else region["monthly"],
        "ui_semiannual": f"{region.get('semiannual', 0):.2f}" if isinstance(region.get("semiannual", 0), float) else region.get("semiannual", 0),
        "ui_annual":     f"{region['annual']:.2f}"  if isinstance(region["annual"], float)  else region["annual"],
        "offers_json":   build_all_offers_json(PRICING_BY_COUNTRY, request),
    }
    return ctx_ui, region


def build_plan_map(region, symbol):
    # Template'te kullanılan asset dosyalarıyla uyumlu
    return {
        "monthly": {
            "key": "monthly",
            "name": _("Monthly"),
            "devices": 5,
            "price": f"{region['monthly']:.2f}" if isinstance(region["monthly"], float) else region["monthly"],
            "interval": _("per month"),
            "poster": "img/monthly.png",
            "webm":   "videos/ribbons/bird-1.webm",
            "mp4":    "videos/ribbons/bird-1.mp4",
            "symbol": symbol,
        },
        "semi": {
            "key": "semi",
            "name": _("6 Months"),
            "devices": 10,
            "price": f"{region['semiannual']:.2f}" if isinstance(region["semiannual"], float) else region["semiannual"],
            "interval": _("per 6 months"),
            "poster": "img/semi-annual.png",
            "webm":   "videos/ribbons/bird-2.webm",
            "mp4":    "videos/ribbons/bird-2.mp4",
            "symbol": symbol,
        },
        "annual": {
            "key": "annual",
            "name": _("Annual"),
            "devices": 20,
            "price": f"{region['annual']:.2f}" if isinstance(region["annual"], float) else region["annual"],
            "interval": _("per year"),
            "poster": "img/annual.png",
            "webm":   "videos/ribbons/bird-3.webm",
            "mp4":    "videos/ribbons/bird-3.mp4",
            "symbol": symbol,
        },
    }

