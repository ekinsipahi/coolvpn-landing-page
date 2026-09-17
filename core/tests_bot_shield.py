"""Bot kalkanı: Turnstile + kapatılmış allauth kayıt sayfası.

NEDEN: 2026-09-09'da biri siteyi kart denemek (carding) için kullandı —
7 dakikada 16 farklı Amex. Stripe Radar TARANAN HER ödeme için 0.05 EUR
yazdığından fatura bize çıktı. Bot ödeme oturumu açamazsa kart deneyemez,
o yüzden fren Stripe'a gitmeden önce duruyor.
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from landing.helpers import turnstile

User = get_user_model()

WITH_KEYS = override_settings(TURNSTILE_SITE_KEY="0x_site", TURNSTILE_SECRET_KEY="0x_secret")
NO_KEYS = override_settings(TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="")


def _cf(success=True):
    """Cloudflare siteverify cevabını taklit eder."""
    r = mock.MagicMock()
    r.read.return_value = json.dumps(
        {"success": success, "error-codes": [] if success else ["invalid-input-response"]}
    ).encode()
    r.__enter__.return_value = r
    return r


class VerifyTests(TestCase):
    @NO_KEYS
    def test_disabled_when_no_secret(self):
        self.assertFalse(turnstile.enabled())
        # Kapalıyken akış bozulmamalı: her jeton geçerli sayılır.
        self.assertTrue(turnstile.verify(""))

    @WITH_KEYS
    def test_empty_token_is_rejected(self):
        self.assertTrue(turnstile.enabled())
        self.assertFalse(turnstile.verify(""))

    @WITH_KEYS
    def test_cloudflare_says_yes(self):
        with mock.patch.object(turnstile.urllib.request, "urlopen", return_value=_cf(True)):
            self.assertTrue(turnstile.verify("tok", "1.2.3.4"))

    @WITH_KEYS
    def test_cloudflare_says_no(self):
        with mock.patch.object(turnstile.urllib.request, "urlopen", return_value=_cf(False)):
            self.assertFalse(turnstile.verify("tok"))

    @WITH_KEYS
    def test_network_failure_fails_CLOSED(self):
        """Açık bırakan bir captcha captcha değildir.

        Cloudflare'a ulaşılamadığı anda geçirseydik, saldırgan tam da o anda
        seli geri gönderir ve faturayı Radar yazardı.
        """
        with mock.patch.object(turnstile.urllib.request, "urlopen",
                               side_effect=OSError("network down")):
            self.assertFalse(turnstile.verify("tok"))

    @WITH_KEYS
    def test_the_secret_is_sent_not_the_site_key(self):
        seen = {}
        def fake(req, timeout=None):
            seen["body"] = req.data.decode()
            return _cf(True)
        with mock.patch.object(turnstile.urllib.request, "urlopen", side_effect=fake):
            turnstile.verify("tok")
        self.assertIn("secret=0x_secret", seen["body"])
        self.assertNotIn("0x_site", seen["body"])


class SignupShieldTests(TestCase):
    URL = "/auth/email-upsert-login/"

    @WITH_KEYS
    def test_no_token_means_no_account(self):
        with mock.patch.object(turnstile, "verify", return_value=False):
            r = self.client.post(self.URL, {"email": "bot@t.test", "password": "Aa123456"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"], "captcha_failed")
        self.assertFalse(User.objects.filter(email="bot@t.test").exists())

    @WITH_KEYS
    def test_valid_token_creates_the_account(self):
        with mock.patch.object(turnstile, "verify", return_value=True):
            r = self.client.post(self.URL, {"email": "insan@t.test", "password": "Aa123456",
                                            "cf-turnstile-response": "tok"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(User.objects.filter(email="insan@t.test").exists())

    @NO_KEYS
    def test_without_keys_the_flow_is_unchanged(self):
        # Anahtar girilmeden deploy edilirse kimse kilitlenmemeli.
        r = self.client.post(self.URL, {"email": "eski@t.test", "password": "Aa123456"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(User.objects.filter(email="eski@t.test").exists())


class CheckoutShieldTests(TestCase):
    """Kart denemenin asıl kapısı: ödeme oturumu açma."""

    def setUp(self):
        self.user = User.objects.create_user(username="kart", email="k@t.test", password="x")
        self.client.force_login(self.user)

    @WITH_KEYS
    def test_bad_token_never_reaches_stripe(self):
        api = mock.MagicMock()
        with mock.patch.object(turnstile, "verify", return_value=False), \
             mock.patch("landing.views._stripe", return_value=api), \
             mock.patch("landing.views.stripe_enabled", return_value=True):
            r = self.client.post("/api/checkout/stripe/", data='{"plan":"monthly"}',
                                 content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"], "captcha_failed")
        # En önemlisi: Stripe'a hiç gidilmemeli — her taranan ödeme 0.05 EUR.
        api.checkout.Session.create.assert_not_called()
        api.Subscription.list.assert_not_called()

    @WITH_KEYS
    def test_good_token_goes_through(self):
        api = mock.MagicMock()
        api.Subscription.list.return_value = mock.MagicMock(data=[])
        api.checkout.Session.create.return_value = mock.MagicMock(url="https://x.test/s")
        with mock.patch.object(turnstile, "verify", return_value=True), \
             mock.patch("landing.views._stripe", return_value=api), \
             mock.patch("landing.views.stripe_enabled", return_value=True), \
             mock.patch("landing.views.ensure_price", return_value="price_1"), \
             mock.patch("landing.views.get_or_create_customer", return_value="cus_1"):
            r = self.client.post("/api/checkout/stripe/", data='{"plan":"monthly","captcha":"tok"}',
                                 content_type="application/json")
        self.assertEqual(r.status_code, 200)
        api.checkout.Session.create.assert_called_once()


class WidgetRenderingTests(TestCase):
    @WITH_KEYS
    def test_pages_render_the_widget_when_configured(self):
        for path in ("/login/", "/payment/"):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                self.assertIn('class="cf-turnstile', body)   # widget'ın kendisi
                self.assertIn("challenges.cloudflare.com/turnstile", body)
                self.assertIn("0x_site", body)

    @NO_KEYS
    def test_nothing_is_rendered_without_keys(self):
        for path in ("/login/", "/payment/"):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                # Widget de script de basılmamalı. JS'teki gizli-input adı
                # ("cf-turnstile-response") kalabilir: widget yokken boş döner.
                self.assertNotIn('class="cf-turnstile', body)
                self.assertNotIn("challenges.cloudflare.com", body)


class AllauthSignupClosedTests(TestCase):
    """Siteden linki olmayan, captcha'sız yan kapı kapatıldı."""

    def test_signup_page_has_no_form(self):
        body = self.client.get("/accounts/signup/").content.decode()
        self.assertNotIn("password1", body)
        self.assertNotIn("<form", body)

    def test_posting_to_it_creates_nothing(self):
        self.client.post("/accounts/signup/",
                         {"email": "yan@kapi.test", "password1": "Aa123456!",
                          "password2": "Aa123456!"})
        self.assertFalse(User.objects.filter(email="yan@kapi.test").exists())


class ThreeDSecureTests(TestCase):
    """Ödeme akışında 3D Secure zorunlu.

    Kart deneyen biri ihraççının doğrulamasını geçemez; geçen gerçek
    ödemede de sahtecilik sorumluluğu ihraççıya geçer. Bu, carding'e karşı
    elimizdeki en sert önlem.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="3ds", email="3ds@t.test",
                                             password="x")
        self.client.force_login(self.user)

    def _create(self):
        api = mock.MagicMock()
        api.Subscription.list.return_value = mock.MagicMock(data=[])
        api.checkout.Session.create.return_value = mock.MagicMock(url="https://x.test/s")
        with mock.patch.object(turnstile, "enabled", return_value=False), \
             mock.patch("landing.views._stripe", return_value=api), \
             mock.patch("landing.views.stripe_enabled", return_value=True), \
             mock.patch("landing.views.ensure_price", return_value="price_1"), \
             mock.patch("landing.views.get_or_create_customer", return_value="cus_1"):
            r = self.client.post("/api/checkout/stripe/", data='{"plan":"monthly"}',
                                 content_type="application/json")
        return r, api.checkout.Session.create.call_args.kwargs

    def test_checkout_asks_for_a_challenge(self):
        r, kwargs = self._create()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            kwargs["payment_method_options"],
            {"card": {"request_three_d_secure": "challenge"}})

    @override_settings(STRIPE_3DS_MODE="automatic")
    def test_mode_can_be_dialled_back_without_a_deploy(self):
        # Dönüşüm belirgin düşerse env ile geri alınabilmeli.
        _, kwargs = self._create()
        self.assertEqual(kwargs["payment_method_options"]["card"]["request_three_d_secure"],
                         "automatic")

    def test_the_value_is_one_stripe_accepts(self):
        # Yanlış bir değer checkout'u 502'ye düşürürdü; kütüphanenin kabul
        # ettiği kümeyle sınırlı kalalım.
        from django.conf import settings as dj
        self.assertIn(getattr(dj, "STRIPE_3DS_MODE", "challenge"),
                      {"any", "automatic", "challenge"})


class ShieldWatchTests(TestCase):
    """Kalkanın kapanması SESSİZ bir olay; cron bunu bağırmalı.

    Sunucuda zamanlayıcı yok, tek düzenli tetikleyici /api/cron/reconcile/.
    Bir deploy env değişkenini düşürürse bunu Radar faturası gelene kadar
    fark etmeyelim diye nöbet oraya kondu.
    """

    def _state(self, **over):
        from landing.helpers.reconcile import _bot_shield_state
        with override_settings(**over):
            return _bot_shield_state()

    @WITH_KEYS
    def test_fully_configured_is_ok(self):
        self.assertEqual(self._state(), "ok")

    def test_each_broken_shape_has_its_own_name(self):
        # Yarım yapılandırmanın iki hali BİRBİRİNDEN FARKLI sonuç doğurur:
        # biri korumayı kaldırır, diğeri herkesi kilitler. Aynı isimle
        # raporlamak, yanlış tarafı düzeltmeye yol açardı.
        self.assertEqual(self._state(TURNSTILE_SITE_KEY="s", TURNSTILE_SECRET_KEY=""),
                         "half_open_no_secret")
        self.assertEqual(self._state(TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="k"),
                         "half_locked_no_sitekey")
        self.assertEqual(self._state(TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY=""),
                         "disabled")

    @WITH_KEYS
    def test_reopened_allauth_signup_is_caught(self):
        self.assertEqual(
            self._state(ACCOUNT_ADAPTER="allauth.account.adapter.DefaultAccountAdapter"),
            "allauth_signup_open")

    @override_settings(TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="")
    def test_cron_reports_and_warns_when_the_shield_is_down(self):
        from landing.helpers import reconcile as rec
        with mock.patch.object(rec, "log") as lg, \
             mock.patch("landing.helpers.stripe_gw.stripe_enabled", return_value=False):
            out = rec.run_reconcile()
        self.assertEqual(out["bot_shield"], "disabled")
        # WARNING, LoggingIntegration üzerinden Sentry olayına dönüşür.
        self.assertTrue(lg.warning.called)
        self.assertIn("BOT KALKANI", lg.warning.call_args[0][0])

    @WITH_KEYS
    def test_cron_stays_quiet_when_everything_is_fine(self):
        from landing.helpers import reconcile as rec
        with mock.patch.object(rec, "log") as lg, \
             mock.patch("landing.helpers.stripe_gw.stripe_enabled", return_value=False):
            out = rec.run_reconcile()
        self.assertEqual(out["bot_shield"], "ok")
        self.assertFalse(lg.warning.called, "her turda gürültü yapmamalı")
