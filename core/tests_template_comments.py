"""Şablonlarda {# ... #} yorum sözdizimi yasak.

Sebebi bir üretim hatası: Django'nun lexer'ı {#...#} çiftini TEK satırda
arar. Birden fazla satıra yayılan bir yorum, yorum sayılmaz — sayfada
müşteriye ham metin olarak görünür. Cihaz bağlama sayfasında tam olarak bu
oldu.

{% comment %} bu tuzağı taşımıyor: çok satırlı yazılabilir ve kapanışı
açıkça {% endcomment %}. Proje tek bir yorum sözdizimi kullanıyor, böylece
karışma ihtimali kalmıyor.
"""

import re

from django.conf import settings
from django.test import SimpleTestCase

# DOTALL: hem tek satırlık gerçek yorumları hem de çok satıra yayıldığı için
# Django'nun yorum saymadığı (ve ham bastığı) blokları yakalar.
COMMENT_RE = re.compile(r"\{#.*?#\}", re.S)

SKIP_DIRS = {".git", "node_modules", "staticfiles", "__pycache__", "venv", ".venv"}


class TemplateCommentSyntaxTests(SimpleTestCase):
    def _templates(self):
        for path in settings.BASE_DIR.rglob("*.html"):
            if SKIP_DIRS & set(path.parts):
                continue
            try:
                yield path, path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

    def test_no_hash_comment_syntax_anywhere(self):
        raw_rendering, single_line = [], []
        for path, text in self._templates():
            rel = path.relative_to(settings.BASE_DIR)
            for match in COMMENT_RE.finditer(text):
                lineno = text.count("\n", 0, match.start()) + 1
                snippet = " ".join(match.group().split())[:90]
                bucket = raw_rendering if "\n" in match.group() else single_line
                bucket.append(f"{rel}:{lineno}: {snippet}")

        problems = []
        if raw_rendering:
            problems.append(
                "ÇOK SATIRLI — Django bunları yorum saymaz, sayfada HAM görünür:\n  "
                + "\n  ".join(raw_rendering))
        if single_line:
            problems.append(
                "{# #} bu projede kullanılmıyor, {% comment %} kullan:\n  "
                + "\n  ".join(single_line))
        self.assertFalse(problems, "\n\n".join(problems))
