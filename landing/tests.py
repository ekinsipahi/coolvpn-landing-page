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
from landing.models import Device, Subscription

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
