"""Markali 404 ve 500 sayfalari.

Ikisinin kosullari BIRBIRINDEN FARKLI ve testler bunu ayirir:
404 request ile render edilir (context processor'lar calisir), 500 ise
request'siz ve context'siz -- orada base.html'e ya da bir context
degiskenine dokunmak, hata sayfasinin kendisini patlatir.
"""
from django.template.loader import get_template
from django.test import SimpleTestCase, TestCase


class NotFoundPageTests(TestCase):
    def test_unknown_url_renders_the_branded_page(self):
        r = self.client.get("/boyle-bir-sayfa-yok/")
        self.assertEqual(r.status_code, 404)
        body = r.content.decode()
        self.assertIn("This page went dark.", body)
        self.assertIn("VPNsterr", body)
        # Django'nun ciplak varsayilani ARTIK gorunmemeli.
        self.assertNotIn("The requested resource was not found on this server.", body)

    def test_it_offers_a_way_out(self):
        body = self.client.get("/yok/").content.decode()
        for href in ('href="/"', "/pricing/", "/support/", "support@vpnsterr.com"):
            with self.subTest(href=href):
                self.assertIn(href, body)

    def test_navbar_and_footer_are_there(self):
        # 404 request ile render edildigi icin tam sayfa iskeleti gelmeli.
        body = self.client.get("/yok/").content.decode()
        self.assertIn("</footer>", body)
        self.assertIn("app.css", body)

    def test_it_is_not_indexable(self):
        body = self.client.get("/yok/").content.decode()
        self.assertIn("noindex", body)

    def test_requested_path_is_escaped(self):
        """Yol kullanicinin yazdigi metin; sayfaya HAM basilamaz."""
        r = self.client.get("/<script>alert(1)</script>/")
        self.assertEqual(r.status_code, 404)
        body = r.content.decode()
        self.assertNotIn("<script>alert(1)</script>", body)

    def test_no_unrendered_template_tags(self):
        body = self.client.get("/yok/").content.decode()
        self.assertNotIn("{%", body)
        self.assertNotIn("{{", body)


class ServerErrorPageTests(SimpleTestCase):
    """500.html'in tek sarti: HICBIR SEYE ihtiyac duymadan render olmak."""

    def test_renders_with_no_request_and_no_context(self):
        # django.views.defaults.server_error tam olarak boyle cagirir.
        html = get_template("500.html").render()
        self.assertIn("Something broke on our end.", html)
        self.assertNotIn("{%", html)
        self.assertNotIn("{{", html)

    def test_the_real_handler_returns_it(self):
        from django.test import RequestFactory
        from django.views.defaults import server_error

        response = server_error(RequestFactory().get("/patlayan-sayfa/"))
        self.assertEqual(response.status_code, 500)
        self.assertIn("Something broke on our end.", response.content.decode())

    def test_it_reassures_about_the_vpn_itself(self):
        # Site coktu diye VPN'i de coktu saniyorlar; sayfa bunu soylemeli.
        html = get_template("500.html").render()
        self.assertIn("Your VPN is not affected.", html)
        self.assertIn("support@vpnsterr.com", html)

    def test_it_stays_dependency_free(self):
        """Regresyon bekcisi.

        500.html'e extends/static/url/trans eklemek, hata sayfasinin kendi
        basina ikinci bir istisna atmasi demek: ziyaretci bembeyaz bir sayfa
        gorur. Kaynakta yorum disinda sablon etiketi olmamali.
        """
        import re
        from pathlib import Path

        from django.conf import settings

        source = (Path(settings.BASE_DIR) / "templates" / "500.html").read_text(encoding="utf-8")
        source = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", source, flags=re.S)
        forbidden = re.findall(r"\{%\s*(extends|static|url|trans|include|blocktrans)\b", source)
        self.assertEqual(forbidden, [], f"500.html bagimsiz kalmali, bulunan: {forbidden}")
        self.assertNotIn("{{", source)

    def test_it_is_not_indexable(self):
        self.assertIn("noindex", get_template("500.html").render())
