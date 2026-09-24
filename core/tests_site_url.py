"""Dış linklerin asla loopback'e düşmemesi.

Bu testlerin varlık sebebi gerçek bir olay: Render'da ``SITE_URL`` env'i
tanımlı değildi, settings ``http://127.0.0.1:8000`` varsayılanına düştü ve
07.09.2026–23.09.2026 arasında 45 gerçek müşteri e-postası tıklanamaz
linklerle gitti. Aynı değer Stripe success_url'ini ve NOWPayments IPN
adresini de beslediği için ödeme akışı da sessizce kırılmıştı.
"""

import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from unittest import mock

from core.site_url import is_loopback, resolve_email_base_url, resolve_site_url

HOST = "vpnsterr.com"


class IsLoopbackTests(SimpleTestCase):
    def test_loopback_forms_are_rejected(self):
        for url in ("http://127.0.0.1:8000", "http://localhost:8000",
                    "https://localhost", "http://0.0.0.0:8000", "http://[::1]:8000"):
            with self.subTest(url=url):
                self.assertTrue(is_loopback(url))

    def test_public_urls_pass(self):
        for url in ("https://vpnsterr.com", "https://pool.vpnsterr.com",
                    "https://staging.vpnsterr.com:8080"):
            with self.subTest(url=url):
                self.assertFalse(is_loopback(url))

    def test_values_without_a_host_are_rejected(self):
        """Şemasız girdi mutlak adres değildir; "vpnsterr.com/pricing/" gibi
        bir SITE_URL sessizce göreli link üretirdi."""
        for url in ("", "   ", "vpnsterr.com", "/pricing/"):
            with self.subTest(url=url):
                self.assertTrue(is_loopback(url))


class ResolveSiteUrlTests(SimpleTestCase):
    def test_production_without_env_falls_back_to_canonical_host(self):
        """Yaşanan arıza: Render'da env yok, varsayılan loopback'ti."""
        self.assertEqual(resolve_site_url("", HOST, debug=False), "https://vpnsterr.com")

    def test_production_refuses_a_loopback_env_value(self):
        """Dev .env'i Render'a kopyalansa bile dışarı 127.0.0.1 çıkmaz."""
        self.assertEqual(resolve_site_url("http://127.0.0.1:8000", HOST, debug=False),
                         "https://vpnsterr.com")

    def test_production_honours_a_real_url(self):
        self.assertEqual(resolve_site_url("https://staging.vpnsterr.com/", HOST, debug=False),
                         "https://staging.vpnsterr.com")

    def test_dev_keeps_loopback_so_local_flows_work(self):
        self.assertEqual(resolve_site_url("http://127.0.0.1:8000", HOST, debug=True),
                         "http://127.0.0.1:8000")


class ResolveEmailBaseUrlTests(SimpleTestCase):
    def test_loopback_is_refused_even_in_dev(self):
        """Alıcı hiçbir zaman bu makinede değil; mailer Resend'e doğrudan POST
        attığı için dev sunucusundan da gerçek mail çıkabiliyor."""
        self.assertEqual(resolve_email_base_url("http://127.0.0.1:8000", HOST),
                         "https://vpnsterr.com")

    def test_empty_falls_back_to_canonical_host(self):
        self.assertEqual(resolve_email_base_url("", HOST), "https://vpnsterr.com")

    def test_explicit_public_override_wins(self):
        self.assertEqual(resolve_email_base_url("https://mail.vpnsterr.com", HOST),
                         "https://mail.vpnsterr.com")


class LiveSettingsTests(SimpleTestCase):
    def test_email_base_url_is_never_loopback(self):
        """Geliştiricinin .env'i ne derse desin mail tabanı publik olmalı."""
        self.assertFalse(is_loopback(settings.EMAIL_BASE_URL), settings.EMAIL_BASE_URL)

    def test_allauth_always_uses_https(self):
        """Parola sıfırlama linki e-postaya gömülüyor; dev'de bile http
        olmamalı, yoksa token ilk adımda düz metin gider."""
        self.assertEqual(settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL, "https")


class RenderedEmailTests(TestCase):
    """Şablonun kendisi loopback link üretmiyor mu — uçtan uca."""

    def _capture(self, fn, *args):
        sent = {}

        def _fake(to, subject, html, text="", reply_to=""):
            sent.update(to=to, subject=subject, html=html, text=text)

        with mock.patch("landing.helpers.mailer.send_email_bg", _fake):
            fn(*args)
        return sent

    def test_welcome_email_links_are_public(self):
        from landing.helpers import mailer

        user = get_user_model().objects.create_user(
            username="linkcheck", email="linkcheck@example.com", password="x")
        sent = self._capture(mailer.send_welcome_email, user)

        self.assertTrue(sent, "mail üretilmedi")
        blob = sent["html"] + sent["text"]
        self.assertNotIn("127.0.0.1", blob)
        self.assertNotIn("localhost", blob)

        links = re.findall(r'href="([^"]+)"', sent["html"])
        self.assertTrue(links, "mailde hiç link yok")
        for link in links:
            with self.subTest(link=link):
                self.assertTrue(link.startswith("https://"), link)


class MailerSourceGuardTests(SimpleTestCase):
    def test_mailer_does_not_read_site_url(self):
        """SITE_URL dev'de loopback olabilir; mailer EMAIL_BASE_URL kullanmalı.
        Kaynak taraması, çünkü geri dönüş tek bir kopyala-yapıştırla oluyor."""
        src = (settings.BASE_DIR / "landing" / "helpers" / "mailer.py").read_text(encoding="utf-8")
        self.assertNotIn("SITE_URL", src)
        self.assertIn("EMAIL_BASE_URL", src)


class HttpsOnlyPolicyTests(SimpleTestCase):
    """Site tek protokol konuşur: https, www'siz.

    Kaynak taraması, çünkü bu kural tek bir kopyala-yapıştırla bozuluyor ve
    sonucu ancak canlıda — Google'ın indekslediği bir canonical'da ya da
    müşteriye giden bir mailde — fark ediliyor.
    """

    OUR_HOSTS = ("vpnsterr.com", "coolvpn.app")
    SCAN_SUFFIXES = (".py", ".html", ".txt", ".xml", ".json", ".md")
    SKIP_DIRS = {".git", "node_modules", "staticfiles", "__pycache__",
                 "venv", ".venv", "migrations", "locale"}

    def _sources(self):
        for path in settings.BASE_DIR.rglob("*"):
            if not path.is_file() or path.suffix not in self.SCAN_SUFFIXES:
                continue
            if self.SKIP_DIRS & set(path.parts):
                continue
            if path.name in {"package-lock.json", "tests_site_url.py"}:
                continue
            try:
                yield path, path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

    def test_our_hosts_are_never_addressed_over_http(self):
        bad = []
        for path, text in self._sources():
            for lineno, line in enumerate(text.splitlines(), 1):
                for host in self.OUR_HOSTS:
                    if f"http://{host}" in line:
                        rel = path.relative_to(settings.BASE_DIR)
                        bad.append(f"{rel}:{lineno}: {line.strip()[:110]}")
        self.assertFalse(bad, "https:// kullan:\n" + "\n".join(bad))

    def test_our_hosts_are_never_prefixed_with_www(self):
        """Tek istisna OLD_HOSTS: orası www'yi apex'e 301'leyen kaynak listesi."""
        bad = []
        for path, text in self._sources():
            for lineno, line in enumerate(text.splitlines(), 1):
                if "OLD_HOSTS" in line:
                    continue
                for host in self.OUR_HOSTS:
                    if f"www.{host}" in line:
                        rel = path.relative_to(settings.BASE_DIR)
                        bad.append(f"{rel}:{lineno}: {line.strip()[:110]}")
        self.assertFalse(bad, "www kullanma, apex kullan:\n" + "\n".join(bad))

    def test_email_base_url_is_https(self):
        self.assertTrue(settings.EMAIL_BASE_URL.startswith("https://"),
                        settings.EMAIL_BASE_URL)
