"""VPNsterr blog: keyword odaklı, SEO'su ölçülen içerik sistemi.

linksterr'deki blog motorundan uyarlandı. Oradan farkları:
- Tek dil (İngilizce): kategori slug'ına göre dil prefix'i üretmiyoruz.
  Site çok dilli olunca CATEGORY_LANG_PREFIX mantığı geri gelebilir.
- AI yazar alanları taşınmadı; asıl istenen keyword + SEO skoru iskeletiydi.

Yazı URL'i: /blog/<kategori-yolu>/<slug>/  (kategori tek seviye ya da
parent/child olabilir).
"""
from __future__ import annotations

import re
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class BlogKeyword(models.Model):
    """Hedeflenen arama terimi. Yazılara M2M bağlanır; hangi keyword'ün
    hangi yazıyla kapsandığı admin'den tek bakışta görülsün diye ayrı model."""

    keyword = models.CharField(max_length=200, unique=True)
    search_volume = models.PositiveIntegerField(null=True, blank=True,
                                                help_text="Aylık arama hacmi")
    difficulty = models.PositiveSmallIntegerField(null=True, blank=True,
                                                  help_text="KD 0-100")
    intent = models.CharField(max_length=20, blank=True, choices=[
        ("buy", "Buy / transactional"),
        ("commercial", "Commercial investigation"),
        ("free", "Free-seeking"),
        ("info", "Informational"),
        ("competitor", "Competitor"),
        ("geo", "Geo / location"),
    ])
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "keywords"
        ordering = ["-search_volume", "keyword"]

    def __str__(self):
        vol = f" [{self.search_volume}/mo]" if self.search_volume else ""
        diff = f" KD:{self.difficulty}" if self.difficulty else ""
        return f"{self.keyword}{vol}{diff}"

    @property
    def is_covered(self) -> bool:
        """Bu keyword'ü hedefleyen yayınlanmış bir yazı var mı?"""
        return self.blogpost_set.filter(status=BlogPost.STATUS_PUBLISHED).exists()


class BlogCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    # Kart/rozet rengi: şablon bunu doğrudan CSS'e basar.
    accent = models.CharField(max_length=20, default="sky", choices=[
        ("sky", "Sky"), ("fuchsia", "Fuchsia"), ("indigo", "Indigo"),
        ("emerald", "Emerald"), ("amber", "Amber"), ("rose", "Rose"),
        ("teal", "Teal"), ("violet", "Violet"),
    ])
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True,
                               blank=True, related_name="children")
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.parent.name} › {self.name}" if self.parent else self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)[:120]
        super().save(*args, **kwargs)

    @property
    def full_path(self) -> str:
        return f"{self.parent.slug}/{self.slug}" if self.parent else self.slug

    @property
    def absolute_url(self) -> str:
        return f"/blog/{self.full_path}/"

    def get_absolute_url(self):
        return self.absolute_url

    @property
    def published_count(self) -> int:
        return self.posts.filter(status=BlogPost.STATUS_PUBLISHED).count()


class BlogPost(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_SCHEDULED = "scheduled"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    ROBOTS_CHOICES = [
        ("index,follow", "index, follow"),
        ("noindex,nofollow", "noindex, nofollow"),
        ("noindex,follow", "noindex, follow"),
    ]

    SCHEMA_CHOICES = [
        ("BlogPosting", "BlogPosting"),
        ("Article", "Article"),
        ("FAQPage", "FAQPage"),
        ("HowTo", "HowTo"),
        ("NewsArticle", "NewsArticle"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.ForeignKey(BlogCategory, on_delete=models.PROTECT,
                                 related_name="posts")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name="blog_posts")

    body = models.TextField(blank=True, help_text="HTML")
    excerpt = models.TextField(blank=True, max_length=500)

    # SEO
    seo_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=165, blank=True)
    canonical_url = models.URLField(blank=True)
    robots = models.CharField(max_length=60, choices=ROBOTS_CHOICES,
                              default="index,follow")
    focus_keyword = models.CharField(max_length=200, blank=True)
    keywords = models.ManyToManyField(BlogKeyword, blank=True)

    schema_type = models.CharField(max_length=30, choices=SCHEMA_CHOICES,
                                   default="BlogPosting")
    json_ld = models.TextField(blank=True)

    featured_image_url = models.URLField(blank=True)
    og_image_url = models.URLField(blank=True)
    og_title = models.CharField(max_length=100, blank=True)
    og_description = models.CharField(max_length=200, blank=True)

    featured = models.BooleanField(default=False,
                                   help_text="Blog ana sayfasında büyük kart")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES,
                              default=STATUS_DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)

    seo_score_cache = models.PositiveSmallIntegerField(default=0, editable=False)
    reading_time = models.PositiveSmallIntegerField(default=0, editable=False)
    internal_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "blog posts"
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            base = slugify(self.title)[:200] or "post"
            slug, n = base, 1
            while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug

        if self.body:
            text = re.sub(r"<[^>]+>", " ", self.body)
            self.reading_time = max(1, round(len(text.split()) / 200))

        # Zamanı gelmiş planlı yazı, kaydedildiğinde yayına geçer.
        if (self.status == self.STATUS_SCHEDULED and self.scheduled_at
                and self.scheduled_at <= timezone.now()):
            self.status = self.STATUS_PUBLISHED
            self.published_at = self.published_at or self.scheduled_at

        if self.status == self.STATUS_PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        self.seo_score_cache = self.get_seo_analysis()["score"]
        super().save(*args, **kwargs)

    # -- türetilmiş alanlar ------------------------------------------- #
    @property
    def absolute_url(self) -> str:
        return f"/blog/{self.category.full_path}/{self.slug}/"

    def get_absolute_url(self):
        return self.absolute_url

    @property
    def effective_seo_title(self) -> str:
        return self.seo_title or self.title

    @property
    def effective_og_image_url(self) -> str:
        return self.og_image_url or self.featured_image_url

    @property
    def effective_canonical(self) -> str:
        if self.canonical_url:
            return self.canonical_url
        site = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
        return f"{site}{self.absolute_url}"

    @property
    def effective_excerpt(self) -> str:
        if self.excerpt:
            return self.excerpt
        text = re.sub(r"<[^>]+>", " ", self.body or "")
        text = re.sub(r"\s+", " ", text).strip()
        return (text[:180] + "…") if len(text) > 180 else text

    @property
    def is_published(self) -> bool:
        return self.status == self.STATUS_PUBLISHED

    # -- SEO puanı ----------------------------------------------------- #
    def get_seo_analysis(self) -> dict:
        """0-100 arası puan + tek tek kontroller.

        Admin'de yazıyı kaydetmeden önce nerede eksik olduğunu göstermek
        için; puan `seo_score_cache`'e yazılır ki listede sıralanabilsin.
        """
        checks: list[tuple[str, str, str]] = []
        score = 0

        body_text = re.sub(r"<[^>]+>", " ", self.body or "").lower()
        fk = (self.focus_keyword or "").lower().strip()

        if fk:
            score += 10
            checks.append(("✓", "Focus keyword set", "green"))
            if fk in (self.title or "").lower():
                score += 15
                checks.append(("✓", "Focus keyword in title", "green"))
            else:
                checks.append(("✗", "Focus keyword NOT in title", "red"))
            if self.meta_description and fk in self.meta_description.lower():
                score += 10
                checks.append(("✓", "Focus keyword in meta description", "green"))
            else:
                checks.append(("✗", "Focus keyword NOT in meta description", "red"))
            if fk in " ".join(body_text.split()[:150]):
                score += 10
                checks.append(("✓", "Focus keyword in first 150 words", "green"))
            else:
                checks.append(("✗", "Focus keyword NOT in first 150 words", "red"))
        else:
            checks.append(("✗", "No focus keyword", "red"))

        if self.meta_description:
            n = len(self.meta_description)
            if 140 <= n <= 165:
                score += 10
                checks.append(("✓", f"Meta description OK ({n} chars)", "green"))
            else:
                score += 5
                checks.append(("~", f"Meta description {n} chars (ideal 140-165)", "yellow"))
        else:
            checks.append(("✗", "No meta description", "red"))

        if self.seo_title:
            n = len(self.seo_title)
            if n <= 70:
                score += 10
                checks.append(("✓", f"SEO title OK ({n} chars)", "green"))
            else:
                score += 3
                checks.append(("~", f"SEO title too long ({n} chars)", "yellow"))
        else:
            score += 3
            checks.append(("~", "No custom SEO title", "yellow"))

        kw = self.keywords.count() if self.pk else 0
        if kw >= 5:
            score += 10
            checks.append(("✓", f"{kw} keywords assigned", "green"))
        elif kw >= 3:
            score += 7
            checks.append(("~", f"{kw} keywords (5+ recommended)", "yellow"))
        elif kw:
            score += 3
            checks.append(("~", f"Only {kw} keyword(s)", "yellow"))
        else:
            checks.append(("✗", "No keywords assigned", "red"))

        links = len(re.findall(r'href=["\']/(?:blog|features|pricing|vpn-extension)', self.body or ""))
        if links >= 4:
            score += 10
            checks.append(("✓", f"{links} internal links", "green"))
        elif links >= 2:
            score += 6
            checks.append(("~", f"{links} internal links (4+ recommended)", "yellow"))
        elif links == 1:
            score += 3
            checks.append(("~", "Only 1 internal link", "yellow"))
        else:
            checks.append(("✗", "No internal links", "red"))

        words = len(body_text.split())
        if words >= 1200:
            score += 10
            checks.append(("✓", f"Excellent length ({words} words)", "green"))
        elif words >= 800:
            score += 7
            checks.append(("✓", f"Good length ({words} words)", "green"))
        elif words >= 400:
            score += 4
            checks.append(("~", f"Could be longer ({words} words)", "yellow"))
        else:
            checks.append(("✗", f"Too short ({words} words)", "red"))

        if self.json_ld:
            score += 5
            checks.append(("✓", "JSON-LD present", "green"))
        else:
            checks.append(("~", "No JSON-LD", "yellow"))

        if self.featured_image_url:
            score += 5
            checks.append(("✓", "Featured image set", "green"))
        else:
            checks.append(("~", "No featured image", "yellow"))

        return {"score": min(score, 100), "checks": checks, "word_count": words,
                "internal_links": links}
