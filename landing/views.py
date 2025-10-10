# landing/views.py
from django.shortcuts import render
from django.utils.translation import gettext as _
from landing.templatetags.pricing import (
    PRICING_BY_COUNTRY,
    detect_country,
    currency_symbol,
    build_all_offers_json,
)
from landing.templatetags.faq_questions import FAQ_QUESTIONS  # <-- EKLENDİ

def home(request):
    user_cc = detect_country(request)
    region = PRICING_BY_COUNTRY.get(user_cc, PRICING_BY_COUNTRY["US"])

    ui_currency = region["currency"]
    ui_symbol = currency_symbol(ui_currency)

    # Teaser için en alakalı 4-6 soruyu priority’ye göre sırala
    faq_sorted = sorted(FAQ_QUESTIONS, key=lambda x: x.get("priority", 999))
    faq_teaser = [q for q in faq_sorted if q.get("teaser", False)][:6]

    ctx = {
        # SEO
        "seo_title": _("CoolVPN — Private Node. Obfuscation. No-Logs."),
        "seo_description": _(
            "Bypass restrictions with audited no-logs VPN. Private node on annual plans. Unlimited bandwidth."
        ),

        # UI: kullanıcının ülkesine göre
        "ui_country": user_cc,
        "ui_currency": ui_currency,
        "ui_currency_symbol": ui_symbol,
        "ui_monthly": f"{region['monthly']:.2f}" if isinstance(region["monthly"], float) else region["monthly"],
        "ui_semiannual": f"{region.get('semiannual', 0):.2f}" if isinstance(region.get("semiannual", 0), float) else region.get("semiannual", 0),
        "ui_annual":  f"{region['annual']:.2f}"  if isinstance(region["annual"], float)  else region["annual"],

        # FAQ: tüm liste + teaser
        "faq_all": faq_sorted,
        "faq_teaser": faq_teaser,

        # JSON-LD: tüm ülkeler (locale-aware absolute URL’lerle)
        "offers_json": build_all_offers_json(PRICING_BY_COUNTRY, request),
    }
    return render(request, "landing/home.html", ctx)
