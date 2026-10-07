"""Mobil uygulama SEO sayfaları — /free-vpn-android/ ve /free-vpn-iphone/.

Ayrı dosyada: views.py zaten çok büyük ve paralel geliştirmede sürekli
çakışıyor (views_faq.py / views_support.py ile aynı gerekçe).

Bu iki sayfanın tek işi Play Store'a trafik taşımak. Anahtar kelime kümesi
"free vpn android / android vpn free / free mobile vpn / vpn apk" etrafında;
iPhone kümesi ayrı sayfada çünkü iOS uygulaması HENÜZ YOK ve aynı sayfada
"indir" ile "yakında"yı yan yana koymak hem kullanıcıyı hem Google'ı yanıltır.

Sayfada BİLEREK olmayan şeyler:
  - Yıldız puanı / indirme sayısı / kullanıcı yorumu. Uygulama yeni, Play'de
    henüz puan yok. Uydurma aggregateRating yapısal veri ihlalidir ve zengin
    sonuçlardan tamamen elenmeye yol açar.
  - APK indirme linki. Dağıtım sadece Play üzerinden; "apk" aramalarını
    SSS'te dürüst cevapla karşılıyoruz, sahte bir indirme ile değil.
"""
from __future__ import annotations

import json

from django.conf import settings
from django.shortcuts import render
from django.urls import reverse

from .helpers.ui import build_ui_context

# Ekran görüntüleri: Play Store asset'lerinden kırpıldı (store-assets/screenshots).
# Oradaki dosyalar çerçeveli ve başlıklı; sayfadaki telefon maketinin içine
# çerçeve-içinde-çerçeve olmasın diye sadece ham ekran alındı.
SCREENS = [
    {
        "img": "img/app/app-home.webp",
        "tab": "One tap",
        "title": "One tap to connect",
        "body": "No server list to study, no config file to import. Open the app, "
                "press the button, you are on an encrypted tunnel.",
    },
    {
        "img": "img/app/app-connected.webp",
        "tab": "Protected",
        "title": "Encrypted, with nothing written down",
        "body": "The session timer is the only thing being counted. We keep no "
                "record of what you connected to, or when.",
    },
    {
        "img": "img/app/app-settings.webp",
        "tab": "Kill switch",
        "title": "Kill switch and auto-reconnect",
        "body": "Get warned the moment the tunnel drops, and reconnect by itself "
                "when you walk from Wi-Fi onto mobile data.",
    },
    {
        "img": "img/app/app-premium.webp",
        "tab": "Premium",
        "title": "Premium removes every ad",
        "body": "Free is ad-supported. Premium drops the ads, unlocks manual "
                "location choice and gives you the full-speed network.",
    },
]

ANDROID_FAQ = [
    (
        "Is the VPNsterr Android app really free?",
        "Yes. The free tier of the Android app has no data cap, no trial countdown "
        "and no credit card. It is funded by ads inside the app, which is why the "
        "Play listing is labelled \"Contains ads\" — we would rather say that out "
        "loud than pretend the app costs nothing to run. Premium removes the ads.",
    ),
    (
        "Do I need an account to use the free VPN on Android?",
        "No. Install it from Google Play and press connect. An account is only "
        "needed if you buy Premium, because the subscription has to belong to "
        "somebody.",
    ),
    (
        "Is there a free VPN APK download for Android?",
        "We only distribute the Android app through Google Play. Sites offering a "
        "\"VPNsterr APK\" are not us, and a repackaged Android VPN APK is one of the most "
        "common ways Android malware gets installed — the app is allowed to see "
        "all your traffic by design, so a tampered build is about the worst thing "
        "you can sideload. Install from the Play Store link on this page.",
    ),
    (
        "Does a free Android VPN keep logs of what I do?",
        "Most do. Ours does not, and that is an architectural choice rather than a "
        "promise: there is no activity log to hand over because the system never "
        "creates one. We keep account and billing records, which is what the law "
        "requires of any company that takes payments.",
    ),
    (
        "What does Premium add on Android?",
        "Three things: every ad disappears, you can pick your exit location "
        "manually instead of using Automatic, and you get the full-speed network. "
        "Premium starts at $4.99 a month and one subscription covers your other "
        "devices too, not just the phone.",
    ),
    (
        "Which Android versions does the app support?",
        "Android 8.0 and newer, on phones and tablets. The app uses the standard "
        "Android VPN service, so it does not need root.",
    ),
    (
        "Can I use the same subscription on my phone and my browser?",
        "Yes. Premium is attached to your account, not to one device, so the same "
        "subscription covers the Android app and the browser extension at the "
        "same time.",
    ),
]

IOS_FAQ = [
    (
        "Is there a VPNsterr app for iPhone yet?",
        "Not yet. A mobile VPN for iOS is in development here, but it has not been "
        "submitted to the App Store. We would rather tell you that than put a dead "
        "\"Download on the App Store\" button on this page.",
    ),
    (
        "What can I use on my iPhone in the meantime?",
        "Nothing of ours, honestly. A VPN on iOS has to be a real app — Apple does "
        "not allow browser extensions to route traffic the way Chrome does on "
        "desktop. If you also have an Android phone or a desktop browser, your "
        "account already works there.",
    ),
    (
        "Will the iPhone app be free too?",
        "That is the plan: the same free tier, the same zero-activity-logs "
        "architecture, and the same Premium subscription shared across your "
        "devices.",
    ),
    (
        "Are free VPN apps on the App Store safe?",
        "Being on the App Store is not an audit. A free iPhone VPN still has to pay "
        "for its servers somehow, and if the answer is not ads or subscriptions it "
        "is usually your data. Read the privacy label, look for a stated no-logs "
        "position, and be suspicious of any VPN that will not say how it makes "
        "money.",
    ),
]


def _faq_schema(pairs):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "inLanguage": "en",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs
        ],
    }


def _breadcrumbs(request, name, url_name):
    base = f"https://{getattr(settings, 'CANONICAL_HOST', 'vpnsterr.com')}"
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": name,
             "item": base + reverse(url_name)},
        ],
    }


def free_vpn_android(request):
    """/free-vpn-android/ — Play Store'a trafik taşıyan ana mobil sayfa."""
    ctx_ui, _region = build_ui_context(request)
    play_url = getattr(settings, "PLAY_STORE_URL", "")

    # MobileApplication: Google'ın uygulama zengin sonucu bunu okur.
    # aggregateRating YOK — bkz. modül docstring'i.
    app_schema = {
        "@context": "https://schema.org",
        "@type": "MobileApplication",
        "name": "VPNsterr — Fast Secure VPN",
        "operatingSystem": "Android 8.0+",
        "applicationCategory": "SecurityApplication",
        "downloadUrl": play_url,
        "installUrl": play_url,
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "USD",
            "description": "Free with ads. Premium subscription from $4.99/month.",
        },
        "publisher": {"@id": f"https://{getattr(settings, 'CANONICAL_HOST', 'vpnsterr.com')}/#org"},
    }

    howto_schema = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": "How to install the free VPNsterr VPN on Android",
        "totalTime": "PT2M",
        "step": [
            {"@type": "HowToStep", "position": 1, "name": "Open the Play Store listing",
             "text": "Tap the Get it on Google Play button on this page.",
             "url": play_url},
            {"@type": "HowToStep", "position": 2, "name": "Install the app",
             "text": "Install VPNsterr — Fast Secure VPN. No account is required for the free tier."},
            {"@type": "HowToStep", "position": 3, "name": "Allow the VPN connection",
             "text": "Press Connect and accept Android's VPN permission prompt. Android shows this once, for every VPN app."},
        ],
    }

    ctx = {
        "seo_title": "Free VPN for Android — Unlimited, No Sign-Up | VPNsterr",
        "seo_description": (
            "Download the free VPN app for Android: unlimited data, no account, zero "
            "activity logs, one tap to connect. Get it on Google Play — Premium from "
            "$4.99/mo removes ads."
        ),
        "screens": SCREENS,
        "faq": ANDROID_FAQ,
        "play_url": play_url,
        "app_store_url": getattr(settings, "APP_STORE_URL", ""),
        "schema_json": json.dumps(
            [app_schema, _faq_schema(ANDROID_FAQ), howto_schema,
             _breadcrumbs(request, "Free VPN for Android", "free_vpn_android")],
            ensure_ascii=False),
        **ctx_ui,
    }
    return render(request, "landing/mobile_app.html", ctx)


def free_vpn_iphone(request):
    """/free-vpn-iphone/ — iOS kümesi. Uygulama yok; sayfa bunu saklamıyor."""
    ctx_ui, _region = build_ui_context(request)
    ctx = {
        "seo_title": "Free VPN for iPhone — iOS App In Development | VPNsterr",
        "seo_description": (
            "The VPNsterr iPhone app is still in development — here is where it "
            "stands, what to watch out for in any free iOS VPN, and what already "
            "works on your other devices today."
        ),
        "faq": IOS_FAQ,
        "play_url": getattr(settings, "PLAY_STORE_URL", ""),
        "app_store_url": getattr(settings, "APP_STORE_URL", ""),
        "schema_json": json.dumps(
            [_faq_schema(IOS_FAQ),
             _breadcrumbs(request, "Free VPN for iPhone", "free_vpn_iphone")],
            ensure_ascii=False),
        **ctx_ui,
    }
    return render(request, "landing/mobile_app_ios.html", ctx)
