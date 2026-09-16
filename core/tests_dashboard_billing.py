"""Dashboard'daki abonelik yonetim kutusu, odeme kaynagina gore degisir.

Bu ayrimin yanlis olmasi kullaniciya PARA kaybettirir: Google Play
aboneligi zaten kendiliginden yenilenirken ona "Extend (crypto)" gostermek,
ustune ikinci bir odeme yaptirmak demektir.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from landing.models import Subscription

User = get_user_model()

# Kart abonesi artık portala gitmeden, panelden tek tıkla iptal ediyor.
CANCEL_STRIPE = "Cancel subscription"
CARD_INVOICES = "Card & invoices"
MANAGE_PLAY = "Manage in Google Play"
EXTEND_CRYPTO = "Extend (crypto)"
SWITCH_CARD = "Switch to card"


class DashboardBillingBoxTests(TestCase):
    def _user_with(self, source, username):
        u = User.objects.create_user(username=username, email=f"{username}@t.test", password="x")
        now = timezone.now()
        Subscription.objects.create(user=u, plan_key="annual", starts_at=now,
                                    ends_at=now + timedelta(days=100), source=source)
        return u

    def _body(self, user):
        self.client.force_login(user)
        r = self.client.get("/dashboard/")
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_stripe_gets_one_click_cancel_and_the_portal(self):
        body = self._body(self._user_with("stripe", "kartli"))
        self.assertIn(CANCEL_STRIPE, body)
        self.assertIn("/api/billing/cancel/", body)
        self.assertIn(CARD_INVOICES, body)      # kart/fatura yönetimi hâlâ portalda
        self.assertNotIn(EXTEND_CRYPTO, body)

    def test_google_play_sends_them_to_google_not_to_a_second_payment(self):
        body = self._body(self._user_with("google_play", "playci"))
        self.assertIn(MANAGE_PLAY, body)
        self.assertIn("play.google.com/store/account/subscriptions", body)
        # En onemlisi: ikinci bir odeme rayi TEKLIF EDILMEMELI.
        self.assertNotIn(EXTEND_CRYPTO, body)
        self.assertNotIn(SWITCH_CARD, body)
        self.assertNotIn(CANCEL_STRIPE, body)

    def test_crypto_offers_extend(self):
        body = self._body(self._user_with("crypto", "kriptocu"))
        self.assertIn(EXTEND_CRYPTO, body)
        self.assertNotIn(CANCEL_STRIPE, body)
        self.assertNotIn(MANAGE_PLAY, body)

    def test_manual_grant_behaves_like_crypto(self):
        # Elle verilen plan da yenilenmez; uzatma teklifi dogru.
        body = self._body(self._user_with("manual", "ellici"))
        self.assertIn(EXTEND_CRYPTO, body)
        self.assertNotIn(MANAGE_PLAY, body)

    def test_free_user_sees_no_management_box(self):
        u = User.objects.create_user(username="bedava2", email="b2@t.test", password="x")
        body = self._body(u)
        for s in (CANCEL_STRIPE, MANAGE_PLAY, EXTEND_CRYPTO):
            with self.subTest(s=s):
                self.assertNotIn(s, body)
