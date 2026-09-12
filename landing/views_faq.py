"""/faq/ — gerçek FAQ sayfası (önceden "coming soon" stub'ıydı).

Ayrı dosyada: views.py zaten çok büyük ve paralel geliştirmede sürekli
çakışıyor. İçerik helpers/faq_content.py'de tek kaynakta.
"""
from __future__ import annotations

import json

from django.shortcuts import render

from .helpers.faq_content import FAQ_GROUPS, faq_count, faq_flat


def faq(request):
    # FAQPage şeması: Google zengin sonuçlarda gösterebilsin diye sayfadaki
    # sorularla BİREBİR aynı metinden üretiliyor.
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faq_flat()
        ],
    }
    return render(request, "landing/faq.html", {
        "faq_groups": FAQ_GROUPS,
        "faq_total": faq_count(),
        "faq_schema_json": json.dumps(schema, ensure_ascii=False),
        "seo_title": "VPNsterr FAQ — free plan, Premium, privacy & setup answers",
        "seo_description": (
            "Straight answers about VPNsterr: is the extension really free and unlimited, "
            "what we log (nothing), how Premium billing and refunds work, and how to set it up."),
    })
