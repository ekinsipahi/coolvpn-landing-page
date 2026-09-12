# core/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """
    Tüm public sayfalar, 20 dil için i18n alternates (hreflang) ile.
    prefix_default_language=False olduğundan 'en' prefixsiz üretilir.
    """
    i18n = True
    alternates = True
    x_default = True
    protocol = "https"

    # (url_name, changefreq, priority) — name "feature:<slug>" ise feature_detail'e çözülür
    FEATURE_SLUGS = ["no-logs", "anonymous-vpn", "kill-switch", "ad-blocker",
                     "speed", "per-tab-routing", "auto-connect", "support",
                     "webrtc", "split-tunneling"]

    PAGES = [
        ("home",                  "weekly",  1.0),
        ("pricing",               "weekly",  0.9),
        ("vpn_extension",         "weekly",  0.9),
        ("free_vpn",              "weekly",  0.9),
        ("best_vpn",              "weekly",  0.8),
        ("best_free_vpn_extension", "weekly", 0.8),
        ("faq",                   "monthly", 0.6),
        ("support",               "monthly", 0.6),
        ("changelog",             "weekly",  0.5),
        ("blog:index",            "weekly",  0.5),
        ("products:desktop",      "monthly", 0.5),
        ("products:mobile",       "monthly", 0.5),
        ("privacy_policy",        "yearly",  0.3),
        ("terms_of_service",      "yearly",  0.3),
        ("refund_policy",         "yearly",  0.3),
        ("acceptable_use",        "yearly",  0.3),
    ]

    def items(self):
        names = [name for name, _, _ in self.PAGES]
        names += [f"feature:{slug}" for slug in self.FEATURE_SLUGS]
        return names

    def location(self, item):
        if item.startswith("feature:"):
            return reverse("feature_detail", kwargs={"slug": item.split(":", 1)[1]})
        return reverse(item)

    def changefreq(self, item):
        if item.startswith("feature:"):
            return "monthly"
        return dict((n, c) for n, c, _ in self.PAGES).get(item, "monthly")

    def priority(self, item):
        if item.startswith("feature:"):
            return 0.7
        return dict((n, p) for n, _, p in self.PAGES).get(item, 0.5)


class BlogPostSitemap(Sitemap):
    """Yayınlanmış blog yazıları.

    i18n=False: blog tek dilde (İngilizce) yazılıyor, statik sayfalardaki
    gibi 20 dillik alternate üretmek yanlış olurdu.
    """
    changefreq = "monthly"
    priority = 0.6
    protocol = "https"

    def items(self):
        from django.utils import timezone

        from blog.models import BlogPost
        return (BlogPost.objects
                .filter(status=BlogPost.STATUS_PUBLISHED,
                        published_at__lte=timezone.now())
                .select_related("category")
                .order_by("-published_at"))

    def location(self, obj):
        return obj.absolute_url

    def lastmod(self, obj):
        return obj.updated_at


class BlogCategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5
    protocol = "https"

    def items(self):
        from blog.models import BlogCategory, BlogPost
        return [c for c in BlogCategory.objects.all()
                if c.posts.filter(status=BlogPost.STATUS_PUBLISHED).exists()]

    def location(self, obj):
        return obj.absolute_url


SITEMAPS = {
    "static": StaticViewSitemap,
    "blog": BlogPostSitemap,
    "blog-categories": BlogCategorySitemap,
}

