"""Cihaz iptali gercekten erisimi kesiyor mu?

Bu akis para demek: `revoke` yalnizca Device.is_active'i False yapiyor, tier ise
kullanici bazinda cozuluyor. Aradaki tek bag token yenilemesi -- dolayisiyla
iptalin ise yarayip yaramadigi tamamen asagidaki testlere bakiyor.
"""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now

from landing import views
from landing.models import Device, PlayPurchase, Subscription

User = get_user_model()
SECRET = "test-shared-secret"


@override_settings(EXTENSION_SHARED_SECRET=SECRET, RESEND_API_KEY="")
class RefreshHonoursRevocationTests(TestCase):
    DEVICE = "device-uuid-0001"

    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@example.com")
        self.sub = Subscription.objects.create(
            user=self.user,
            plan_key="annual",
            starts_at=now() - timedelta(days=1),
            ends_at=now() + timedelta(days=300),
            source="stripe",
        )

    def token(self, device_id=DEVICE, tier="premium"):
        exp = int((now() + timedelta(days=300)).timestamp())
        return views._mint_account_token(self.user, device_id, tier, exp)

    def refresh(self, token):
        return self.client.post(
            reverse("extension_link_refresh"),
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def active_device(self):
        return Device.objects.create(
            user=self.user, client_uuid=self.DEVICE,
            platform="android", name="Android app", is_active=True,
        )

    # -- the thing that was broken ---------------------------------------

    def test_a_revoked_device_is_refused(self):
        device = self.active_device()
        device.is_active = False
        device.save(update_fields=["is_active"])

        res = self.refresh(self.token())
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["error"], "device_revoked")

    def test_a_revoked_device_gets_no_fresh_premium_token(self):
        """The real damage: refusing must also mean handing out nothing."""
        device = self.active_device()
        device.is_active = False
        device.save(update_fields=["is_active"])

        body = self.refresh(self.token()).json()
        self.assertNotIn("token", body)
        self.assertNotEqual(body.get("plan"), "premium")

    # -- and what must keep working --------------------------------------

    def test_an_active_device_still_refreshes_to_premium(self):
        self.active_device()
        res = self.refresh(self.token())
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["plan"], "premium")
        self.assertTrue(body["token"])

    def test_a_device_that_was_never_registered_is_not_a_revocation(self):
        """Linking skips the Device row when the plan's cap is full but still
        issues a token. Treating "no row" as revoked would lock those users into
        a loop they cannot leave: link -> 401 -> wiped -> link -> 401."""
        self.assertFalse(Device.objects.filter(client_uuid=self.DEVICE).exists())
        res = self.refresh(self.token())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["plan"], "premium")

    def test_an_expired_subscription_drops_to_free(self):
        self.active_device()
        self.sub.ends_at = now() - timedelta(days=1)
        self.sub.save(update_fields=["ends_at"])

        body = self.refresh(self.token()).json()
        self.assertEqual(body["plan"], "free")
        self.assertIsNone(body["expires_at"])

    def test_a_token_bound_to_no_device_is_refused(self):
        res = self.refresh(self.token(device_id=""))
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["error"], "device_unbound")

    def test_a_forged_token_is_refused(self):
        good = self.token()
        payload, _sig = good.split(".", 1)
        res = self.refresh(f"{payload}.AAAAtamperedAAAA")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["error"], "invalid_token")


@override_settings(EXTENSION_SHARED_SECRET=SECRET, RESEND_API_KEY="")
class PlayPurchaseDeviceCannotBeRevokedTests(TestCase):
    """Play aboneliginin alindigi cihaz dashboard'dan silinememeli.

    Cihazi iptal etmek Google'daki aboneligi iptal etmiyor. Ikisi ayrilirsa
    kullanici parasini odedigi cihazda free'ye duser ve bunu hicbir taraftan
    duzeltemez -- dogrudan iade talebi demek.
    """
    DEVICE = "play-device-0001"
    OTHER = "other-device-0002"

    def setUp(self):
        self.user = User.objects.create_user(username="p", email="p@example.com")
        self.client.force_login(self.user)
        self.sub = Subscription.objects.create(
            user=self.user, plan_key="monthly",
            starts_at=now() - timedelta(days=1),
            ends_at=now() + timedelta(days=29),
            source="google_play",
        )
        self.device = Device.objects.create(
            user=self.user, client_uuid=self.DEVICE,
            platform="android", name="Android app", is_active=True,
        )
        PlayPurchase.objects.create(
            purchase_token="tok-abc",
            user=self.user,
            product_id="premium_monthly",
            plan_key="monthly",
            state=PlayPurchase.STATE_ACTIVE,
            expires_at=now() + timedelta(days=29),
            device_uuid=self.DEVICE,
            subscription=self.sub,
        )

    def revoke(self, uuid):
        return self.client.post(
            reverse("device_revoke"), {"uuid": uuid},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_the_purchasing_device_is_refused(self):
        res = self.revoke(self.DEVICE)
        self.assertEqual(res.status_code, 409)
        self.device.refresh_from_db()
        self.assertTrue(self.device.is_active)

    def test_the_refusal_says_where_to_go_instead(self):
        body = self.revoke(self.DEVICE).json()
        self.assertIn("Play Store", body["error"])

    def test_another_device_on_the_same_account_still_revokes(self):
        other = Device.objects.create(
            user=self.user, client_uuid=self.OTHER,
            platform="android", name="Old phone", is_active=True,
        )
        res = self.revoke(self.OTHER)
        self.assertEqual(res.status_code, 200)
        other.refresh_from_db()
        self.assertFalse(other.is_active)

    def test_an_expired_play_purchase_no_longer_protects_the_device(self):
        """Once the subscription is over there is nothing left to protect."""
        PlayPurchase.objects.update(
            expires_at=now() - timedelta(days=1),
            state=PlayPurchase.STATE_EXPIRED,
        )
        res = self.revoke(self.DEVICE)
        self.assertEqual(res.status_code, 200)
        self.device.refresh_from_db()
        self.assertFalse(self.device.is_active)

    def test_a_stripe_subscription_does_not_lock_the_device(self):
        """Bought on the site: no Play binding, so revoking is the user's call."""
        PlayPurchase.objects.all().delete()
        self.sub.source = "stripe"
        self.sub.save(update_fields=["source"])
        res = self.revoke(self.DEVICE)
        self.assertEqual(res.status_code, 200)


@override_settings(EXTENSION_SHARED_SECRET=SECRET, RESEND_API_KEY="")
class LinkedDeviceIsNamedByPlatformTests(TestCase):
    """Baglanan cihaz dashboard'da dogru isimle gorunmeli.

    Bu sayfayi hem eklenti hem Android uygulamasi kullaniyor. Once her cihaz
    "Browser extension" diye kaydediliyordu; telefonunu listede bulamayan biri
    yanlis satiri iptal eder -- ve Play aboneligini tasiyan cihaz o satirsa
    kendi erisimini keser.
    """
    NONCE = "n" * 32

    def setUp(self):
        self.user = User.objects.create_user(username="d", email="d@example.com")
        self.client.force_login(self.user)

    def link(self, device_id, platform=None):
        data = {"nonce": self.NONCE, "device_id": device_id}
        if platform is not None:
            data["platform"] = platform
        return self.client.post(reverse("extension_link"), data)

    def device(self, device_id):
        return Device.objects.get(user=self.user, client_uuid=device_id)

    def test_the_android_app_is_named_as_such(self):
        self.link("dev-android", platform="android")
        d = self.device("dev-android")
        self.assertEqual(d.platform, "android")
        self.assertEqual(d.name, "Android app")

    def test_the_extension_is_still_the_extension(self):
        self.link("dev-ext", platform="browser")
        d = self.device("dev-ext")
        self.assertEqual(d.platform, "browser")
        self.assertEqual(d.name, "Browser extension")

    def test_no_hint_falls_back_to_browser(self):
        # Older extension builds send nothing; they must keep working.
        self.link("dev-old")
        self.assertEqual(self.device("dev-old").platform, "browser")

    def test_an_unknown_hint_cannot_write_free_text_into_the_list(self):
        self.link("dev-evil", platform="<script>alert(1)</script>")
        d = self.device("dev-evil")
        self.assertEqual(d.platform, "browser")
        self.assertEqual(d.name, "Browser extension")
