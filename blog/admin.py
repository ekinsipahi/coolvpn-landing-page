"""Blog admin: keyword havuzu + yazı editörü + canlı SEO puanı."""
from __future__ import annotations

from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html, format_html_join

from .models import BlogCategory, BlogKeyword, BlogPost


def _score_badge(score: int) -> str:
    color = "#12b76a" if score >= 80 else "#f79009" if score >= 55 else "#e11d48"
    return format_html(
        '<span style="display:inline-block;min-width:38px;text-align:center;'
        'padding:2px 8px;border-radius:9px;background:{};color:#fff;font-weight:700">{}</span>',
        color, score)


@admin.register(BlogKeyword)
class BlogKeywordAdmin(admin.ModelAdmin):
    list_display = ("keyword", "intent", "search_volume", "difficulty",
                    "coverage", "created_at")
    list_filter = ("intent", "created_at")
    search_fields = ("keyword", "notes")
    ordering = ("-search_volume", "keyword")
    list_per_page = 100

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _covered=Count("blogpost", filter=Q(blogpost__status=BlogPost.STATUS_PUBLISHED)))

    @admin.display(description="Covered", ordering="_covered")
    def coverage(self, obj):
        n = getattr(obj, "_covered", 0)
        if n:
            return format_html('<span style="color:#12b76a;font-weight:600">✓ {} post(s)</span>', n)
        return format_html('<span style="color:#e11d48">— not covered</span>')


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("__str__", "slug", "accent", "sort_order", "published_count")
    list_editable = ("sort_order",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")

    @admin.display(description="Published")
    def published_count(self, obj):
        return obj.published_count


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "seo_badge", "reading_time",
                    "featured", "published_at")
    list_filter = ("status", "featured", "category", "published_at")
    search_fields = ("title", "body", "focus_keyword", "meta_description")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("keywords",)
    autocomplete_fields = ("category",)
    date_hierarchy = "published_at"
    readonly_fields = ("seo_report", "reading_time", "created_at", "updated_at")
    list_per_page = 50

    fieldsets = (
        ("Content", {
            "fields": ("title", "slug", "category", "author", "excerpt", "body"),
        }),
        ("SEO — canlı puan", {
            "fields": ("seo_report", "focus_keyword", "keywords", "seo_title",
                       "meta_description", "canonical_url", "robots"),
            "description": "Puan kaydettikçe güncellenir. 80+ hedefle.",
        }),
        ("Schema & social", {
            "classes": ("collapse",),
            "fields": ("schema_type", "json_ld", "featured_image_url",
                       "og_image_url", "og_title", "og_description"),
        }),
        ("Publishing", {
            "fields": ("status", "featured", "published_at", "scheduled_at"),
        }),
        ("Internal", {
            "classes": ("collapse",),
            "fields": ("internal_notes", "reading_time", "created_at", "updated_at"),
        }),
    )

    @admin.display(description="SEO", ordering="seo_score_cache")
    def seo_badge(self, obj):
        return _score_badge(obj.seo_score_cache)

    @admin.display(description="SEO analysis")
    def seo_report(self, obj):
        if obj.pk is None:
            return "Kaydet, puan burada çıksın."
        a = obj.get_seo_analysis()
        colors = {"green": "#12b76a", "yellow": "#f79009", "red": "#e11d48"}
        rows = format_html_join(
            "", '<li style="color:{};margin:2px 0">{} {}</li>',
            ((colors.get(c, "#666"), mark, text) for mark, text, c in a["checks"]))
        return format_html(
            '<div style="max-width:560px">{}<p style="margin:8px 0 4px;color:#666">'
            '{} words · {} internal links</p><ul style="margin:0;padding-left:18px;'
            'list-style:none">{}</ul></div>',
            _score_badge(a["score"]), a["word_count"], a["internal_links"], rows)

    def save_model(self, request, obj, form, change):
        if obj.author_id is None:
            obj.author = request.user
        super().save_model(request, obj, form, change)
