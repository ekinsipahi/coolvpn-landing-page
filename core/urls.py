# core/urls.py  (PROJE urls’i)
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from landing.views import google_finish

Stub = TemplateView.as_view

# --- namespaced stub grupları ---
features_patterns = (
    [
        # SEO: coolvpn.app doneminden indexli, artik silinmis sayfalar -> canli esdegerlere 301
        path("stealth/", RedirectView.as_view(url="/features/no-logs/", permanent=True), name="stealth"),
        path("dedicated-ip/", RedirectView.as_view(url="/pricing/", permanent=True), name="dedicated_ip"),
        # Bu ikisinin gercek sayfalari landing'de /features/<slug>/ altinda yasiyor
        path("webrtc/", RedirectView.as_view(url="/features/webrtc/", permanent=True), name="webrtc"),
        path("split-tunneling/", RedirectView.as_view(url="/features/split-tunneling/", permanent=True), name="split_tunnel"),
    ],
    "features",
)

advantages_patterns = (
    [
        path("no-logs/", RedirectView.as_view(url="/features/no-logs/", permanent=True), name="no_logs"),
        path("jurisdiction/", RedirectView.as_view(url="/features/no-logs/", permanent=True), name="jurisdiction"),
        path("speed/", RedirectView.as_view(url="/features/speed/", permanent=True), name="speed"),
    ],
    "advantages",
)

products_patterns = (
    [
        path("extension/", RedirectView.as_view(url="/vpn-extension/", permanent=True), name="extension"),
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

from django.contrib.sitemaps.views import sitemap as sitemap_view
from core.sitemaps import SITEMAPS
from landing.views_faq import faq as faq_view
from landing.views_changelog import changelog as changelog_view

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),  # dil değişimi
    # SEO: dil prefixsiz, tüm dilleri hreflang alternates ile listeler
    path("sitemap.xml", sitemap_view, {"sitemaps": SITEMAPS},
         name="django.contrib.sitemaps.views.sitemap"),
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
    path("faq/", faq_view, name="faq"),
    path("changelog/", changelog_view, name="changelog"),
    # namespaced groups
    path("features/", include(features_patterns, namespace="features")),
    path("advantages/", include(advantages_patterns, namespace="advantages")),
    path("products/", include(products_patterns, namespace="products")),
    path("blog/", include("blog.urls")),
    prefix_default_language=False,
)
