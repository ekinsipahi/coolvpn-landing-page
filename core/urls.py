# core/urls.py  (PROJE urls’i)
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import TemplateView
from landing.views import google_finish

Stub = TemplateView.as_view

# --- namespaced stub grupları ---
features_patterns = (
    [
        path(
            "stealth/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "Stealth / Obfuscation",
                    "subtitle": "Engineered to maximize access on restricted networks",
                },
            ),
            name="stealth",
        ),
        path(
            "dedicated-ip/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "Dedicated IP / Private Node",
                    "subtitle": "Annual plans include your own private endpoint",
                },
            ),
            name="dedicated_ip",
        ),
        path(
            "webrtc/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "WebRTC Leak Block",
                    "subtitle": "Prevent IP leaks in modern browsers",
                },
            ),
            name="webrtc",
        ),
        path(
            "split-tunneling/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "Split Tunneling / Whitelist",
                    "subtitle": "Choose what routes through VPN",
                },
            ),
            name="split_tunnel",
        ),
    ],
    "features",
)

advantages_patterns = (
    [
        path(
            "no-logs/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "No-Logs by design",
                    "subtitle": "We minimize data by architecture",
                },
            ),
            name="no_logs",
        ),
        path(
            "jurisdiction/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "Privacy-friendly jurisdiction",
                    "subtitle": "Favorable legal base outside surveillance alliances",
                },
            ),
            name="jurisdiction",
        ),
        path(
            "speed/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "Unlimited bandwidth & high throughput",
                    "subtitle": "Optimized network for speed",
                },
            ),
            name="speed",
        ),
    ],
    "advantages",
)

products_patterns = (
    [
        path(
            "extension/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "Browser Extension",
                    "subtitle": "Lightweight, control per tab/app",
                },
            ),
            name="extension",
        ),
        path(
            "desktop/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "Desktop App",
                    "subtitle": "System-wide protection",
                },
            ),
            name="desktop",
        ),
        path(
            "mobile/",
            Stub(
                template_name="stubs/simple.html",
                extra_context={"title": "Mobile App", "subtitle": "iOS & Android"},
            ),
            name="mobile",
        ),
    ],
    "products",
)

blog_patterns = (
    [
        path(
            "",
            Stub(
                template_name="stubs/simple.html",
                extra_context={
                    "title": "Blog",
                    "subtitle": "Guides, updates, transparency notes",
                },
            ),
            name="index",
        ),
    ],
    "blog",
)

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),  # dil değişimi
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    # KÖK: landing uygulamasını köke bağla
    path("", include("landing.urls")),
    
    path("accounts/", include("allauth.urls")),
    

    path(
        "logout/",
        Stub(
            template_name="stubs/simple.html",
            extra_context={
                "title": "Signed out",
                "subtitle": "You have been signed out",
            },
        ),
        name="logout",
    ),
    path(
        "account/settings/",
        Stub(
            template_name="stubs/simple.html",
            extra_context={
                "title": "Account Settings",
                "subtitle": "Manage your account",
            },
        ),
        name="account_settings",
    ),
    # marketing
    path(
        "faq/",
        Stub(
            template_name="stubs/simple.html",
            extra_context={"title": "FAQ", "subtitle": "Answers to common questions"},
        ),
        name="faq",
    ),
    # namespaced groups
    path("features/", include(features_patterns, namespace="features")),
    path("advantages/", include(advantages_patterns, namespace="advantages")),
    path("products/", include(products_patterns, namespace="products")),
    path("blog/", include(blog_patterns, namespace="blog")),
    prefix_default_language=False,
)
