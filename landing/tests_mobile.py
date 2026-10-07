"""/free-vpn-android/ ve /free-vpn-iphone/ testleri.

Buradaki testlerin çoğu "sayfa 200 dönüyor mu" değil; yanlış giderse pahalıya
mal olacak ÜÇ şeyi bekliyor:

  1. Uydurma yıldız puanı / yorum sayısı yapısal veriye sızmasın. Google'ın
     yapısal veri politikası bunu doğrudan ihlal sayıyor ve cezası sitenin
     zengin sonuçlardan tamamen elenmesi.
  2. iOS uygulaması yokken sayfaya ölü bir App Store linki girmesin. Hem
     kullanıcıyı kandırır hem Apple'ın marka kurallarını çiğner.
  3. Sayfadaki SSS metni ile JSON-LD'deki SSS metni birbirinden ayrışmasın.
     İkisi aynı Python listesinden üretiliyor; biri elle düzenlenirse test
     patlasın.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from landing.views_mobile import ANDROID_FAQ, IOS_FAQ, SCREENS


def _schema_blocks(resp) -> list:
    """Sayfaya özel JSON-LD blokları.

    Yanıtın HTML'ini değil view context'indeki `schema_json`'ı okuyor: base.html
    her sayfaya bir de site geneli Organization şeması basıyor, onu da
    toplasaydık testler bu sayfayla ilgisiz bir düğüm yüzünden kırılırdı.
    """
    return json.loads(resp.context["schema_json"])


class AndroidPageTests(TestCase):
    def setUp(self):
        self.resp = self.client.get(reverse("free_vpn_android"))
        self.html = self.resp.content.decode()

    def test_page_renders(self):
        self.assertEqual(self.resp.status_code, 200)

    def test_h1_carries_the_primary_keyword(self):
        # "free vpn for android" bu sayfanin tek hedef kumesi; H1'den duserse
        # sayfanin var olma sebebi kalmiyor.
        h1 = self.html.split("<h1", 1)[1].split("</h1>", 1)[0].lower()
        self.assertIn("free vpn for android", h1)

    def test_play_store_link_is_present_and_real(self):
        self.assertIn(settings.PLAY_STORE_URL, self.html)
        self.assertIn("com.vpnsterr.app", settings.PLAY_STORE_URL)

    def test_play_package_matches_billing_verification(self):
        # Link baska bir uygulamayi gosterirse kullanici yanlis uygulamayi
        # kurar ve abonelik dogrulamasi hicbir zaman eslesmez.
        from landing.helpers import play_billing  # noqa: F401
        self.assertIn(
            getattr(settings, "GOOGLE_PLAY_PACKAGE_NAME", ""),
            settings.PLAY_STORE_URL,
        )

    def test_every_screenshot_file_exists_on_disk(self):
        for s in SCREENS:
            found = any((Path(d) / s["img"]).is_file() for d in settings.STATICFILES_DIRS)
            self.assertTrue(found, f"missing static file: {s['img']}")
            self.assertIn(s["img"], self.html)

    def test_schema_has_the_expected_types(self):
        types = {b.get("@type") for b in _schema_blocks(self.resp)}
        self.assertEqual(
            types, {"MobileApplication", "FAQPage", "HowTo", "BreadcrumbList"})

    def test_no_invented_ratings_anywhere(self):
        # Uygulama yeni, Play'de henuz puan yok. Uydurma aggregateRating
        # yapisal veri ihlali; buraya kazara girmesin.
        blob = json.dumps(_schema_blocks(self.resp))
        for forbidden in ("aggregateRating", "ratingValue", "reviewCount", "ratingCount"):
            self.assertNotIn(forbidden, blob)

    def test_faq_on_the_page_matches_the_faq_in_the_schema(self):
        faq = next(b for b in _schema_blocks(self.resp) if b["@type"] == "FAQPage")
        self.assertEqual(
            [q["name"] for q in faq["mainEntity"]],
            [q for q, _ in ANDROID_FAQ],
        )
        for question, answer in ANDROID_FAQ:
            self.assertIn(answer[:60], self.html)

    def test_ios_badge_says_coming_soon_and_links_nowhere_external(self):
        self.assertIn("Coming soon to", self.html)
        self.assertNotIn("apps.apple.com", self.html)

    @override_settings(APP_STORE_URL="https://apps.apple.com/app/id123456789")
    def test_ios_badge_becomes_a_real_link_once_the_app_ships(self):
        # settings.APP_STORE_URL'i doldurmak TEK degisiklik olmali; rozet
        # kendiliginden indirme butonuna donmezse bu sozu tutmuyoruz.
        html = self.client.get(reverse("free_vpn_android")).content.decode()
        self.assertIn("https://apps.apple.com/app/id123456789", html)
        self.assertIn("Download on the", html)
        self.assertNotIn("Coming soon to", html)

    def test_the_ads_disclosure_is_not_quietly_dropped(self):
        # Play listesinde "Contains ads" yaziyor. Sayfa bunu saklarsa reklam
        # goren kullanici kandirilmis olur.
        self.assertIn("ad-supported", self.html)


class IphonePageTests(TestCase):
    def setUp(self):
        self.resp = self.client.get(reverse("free_vpn_iphone"))
        self.html = self.resp.content.decode()

    def test_page_renders(self):
        self.assertEqual(self.resp.status_code, 200)

    def test_no_dead_app_store_link_while_the_app_does_not_exist(self):
        self.assertEqual(getattr(settings, "APP_STORE_URL", ""), "")
        self.assertNotIn("apps.apple.com", self.html)
        self.assertNotIn("itunes.apple.com", self.html)

    def test_the_page_says_the_app_is_not_out(self):
        self.assertIn("In development", self.html)

    def test_it_sends_people_to_the_app_that_does_exist(self):
        self.assertIn(reverse("free_vpn_android"), self.html)

    def test_faq_matches_the_schema(self):
        faq = next(b for b in _schema_blocks(self.resp) if b["@type"] == "FAQPage")
        self.assertEqual(
            [q["name"] for q in faq["mainEntity"]], [q for q, _ in IOS_FAQ])



class MobileRoutingTests(TestCase):
    def test_old_products_mobile_stub_redirects_permanently(self):
        resp = self.client.get("/products/mobile/")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp["Location"], reverse("free_vpn_android"))

    def test_sitemap_lists_the_new_pages_and_drops_the_redirect(self):
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/free-vpn-android/", body)
        self.assertIn("/free-vpn-iphone/", body)
        # Yonlendirme URL'i sitemap'te kalirsa Google'a celiskili sinyal gider.
        self.assertNotIn("/products/mobile/", body)

    def test_navigation_points_at_the_new_pages(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn(reverse("free_vpn_android"), html)
        self.assertIn(reverse("free_vpn_iphone"), html)
