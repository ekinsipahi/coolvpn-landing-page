"""Blog görünümleri: liste (arama + kategori filtresi), kategori, detay."""
from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import BlogCategory, BlogPost

PER_PAGE = 9


def _published():
    return (BlogPost.objects
            .filter(status=BlogPost.STATUS_PUBLISHED, published_at__lte=timezone.now())
            .select_related("category", "author"))


def _category_by_path(path: str) -> BlogCategory:
    """"parent/child" ya da "slug" → kategori."""
    parts = path.strip("/").split("/")
    if len(parts) == 2:
        return get_object_or_404(BlogCategory, slug=parts[1], parent__slug=parts[0])
    return get_object_or_404(BlogCategory, slug=parts[0], parent__isnull=True)


def _sidebar_categories():
    return (BlogCategory.objects
            .annotate(n=Count("posts", filter=Q(posts__status=BlogPost.STATUS_PUBLISHED)))
            .filter(n__gt=0).order_by("sort_order", "name"))


def blog_index(request):
    """/blog/ — arama + kategori filtresi + öne çıkan yazı."""
    q = (request.GET.get("q") or "").strip()[:80]
    posts = _published()
    if q:
        posts = posts.filter(
            Q(title__icontains=q) | Q(excerpt__icontains=q)
            | Q(body__icontains=q) | Q(keywords__keyword__icontains=q)
        ).distinct()

    # Öne çıkan yazı yalnızca filtrelenmemiş ilk sayfada; aramada kafa karıştırır.
    featured = None
    page_no = request.GET.get("page") or "1"
    if not q and page_no == "1":
        featured = posts.filter(featured=True).first() or posts.first()
        if featured:
            posts = posts.exclude(pk=featured.pk)

    page = Paginator(posts, PER_PAGE).get_page(page_no)
    return render(request, "blog/index.html", {
        "featured": featured,
        "page_obj": page,
        "posts": page.object_list,
        "categories": _sidebar_categories(),
        "q": q,
        "total": _published().count(),
        "seo_title": "VPNsterr Blog — privacy guides, VPN how-tos & product news",
        "seo_description": (
            "Straight-talking guides on staying private online: how VPNs work, "
            "what no-logs really means, browser privacy, and what we're shipping next."),
    })


def blog_category(request, category_path):
    return _render_category(request, _category_by_path(category_path))


def _render_category(request, category):
    child_ids = list(category.children.values_list("id", flat=True))
    posts = _published().filter(Q(category=category) | Q(category_id__in=child_ids))
    page = Paginator(posts, PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "blog/category.html", {
        "category": category,
        "page_obj": page,
        "posts": page.object_list,
        "categories": _sidebar_categories(),
        "seo_title": f"{category.name} — VPNsterr Blog",
        "seo_description": category.description[:165] or
            f"{category.name} guides and articles from VPNsterr.",
    })


def blog_two_segment(request, first, second):
    """/blog/<a>/<b>/ — önce "kategori a + yazı b", olmazsa "a/b iç kategorisi".

    Tek görünümde ayırmak zorundayız: Django bir görünüm 404 attığında
    sonraki URL desenine geçmez, dolayısıyla iki ayrı desenle çözülemiyor.
    """
    post = _published().filter(slug=second, category__slug=first).first()
    if post is not None:
        return _render_detail(request, post)
    category = get_object_or_404(BlogCategory, slug=second, parent__slug=first)
    return _render_category(request, category)


def blog_nested_detail(request, parent_slug, child_slug, post_slug):
    category = get_object_or_404(BlogCategory, slug=child_slug, parent__slug=parent_slug)
    post = get_object_or_404(_published(), slug=post_slug, category=category)
    return _render_detail(request, post)


def _render_detail(request, post):
    category = post.category
    related = (_published().filter(category=category)
               .exclude(pk=post.pk).order_by("-published_at")[:3])
    return render(request, "blog/detail.html", {
        "post": post,
        "category": category,
        "related": related,
        "seo_title": post.effective_seo_title,
        "seo_description": post.meta_description or post.effective_excerpt,
    })
