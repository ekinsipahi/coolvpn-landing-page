"""/changelog/ — sevk edilenlerin listesi.

Rozet etiketleri şablonda değil BURADA çözülüyor: Django'da sözlükten
değişken anahtarla değer okuyan bir filtre yok, uydurmak yerine veriyi
hazır hâlde göndermek daha basit.
"""
from __future__ import annotations

from django.shortcuts import render

from .helpers.changelog_content import (
    COMING_NEXT,
    KIND_LABELS,
    RELEASES,
    latest_version,
)


def changelog(request):
    releases = [
        {
            "version": rel["version"],
            "date": rel["date"],
            "title": rel["title"],
            "entries": [
                {"label": KIND_LABELS.get(kind, (kind.title(), "sky"))[0],
                 "accent": KIND_LABELS.get(kind, (kind.title(), "sky"))[1],
                 "text": text}
                for kind, text in rel["entries"]
            ],
        }
        for rel in RELEASES
    ]
    return render(request, "landing/changelog.html", {
        "releases": releases,
        "coming_next": COMING_NEXT,
        "seo_title": f"VPNsterr Changelog — what's new in v{latest_version()}",
        "seo_description": (
            "Every VPNsterr release in one place: new features, improvements, fixes "
            "and security changes — plus what we're working on next."),
    })
