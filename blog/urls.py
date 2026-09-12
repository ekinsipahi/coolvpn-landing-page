"""Blog URL'leri.

  /blog/                          → index
  /blog/<slug>/                   → kategori
  /blog/<a>/<b>/                  → önce "kategori a + yazı b", olmazsa
                                    "iç kategori a/b"  (bkz. views.blog_two_segment)
  /blog/<a>/<b>/<slug>/           → iç kategoride yazı

`index` adı korunuyor: navbar, footer ve sitemap zaten `blog:index` diyor.

NEDEN AYRI BİR DAĞITICI: iki segmentli yol hem "kategori/yazı" hem
"üst-kategori/alt-kategori" olabiliyor. Django, bir görünüm 404 atınca
sonraki desene DÜŞMEZ — bu yüzden ayrımı görünüm içinde yapıyoruz.
"""
from django.urls import path, re_path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.blog_index, name="index"),
    re_path(r"^(?P<parent_slug>[\w-]+)/(?P<child_slug>[\w-]+)/(?P<post_slug>[\w-]+)/$",
            views.blog_nested_detail, name="post_detail_nested"),
    re_path(r"^(?P<first>[\w-]+)/(?P<second>[\w-]+)/$",
            views.blog_two_segment, name="post_detail"),
    re_path(r"^(?P<category_path>[\w-]+)/$",
            views.blog_category, name="category"),
]
