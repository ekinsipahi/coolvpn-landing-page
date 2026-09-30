"""Tests for the evidence that has to outlive an account.

Every one of these protects a decision we could not make on 2026-09-16, when a
customer was charged twice, deleted his account and left nothing behind.
"""
import hashlib
import hmac
import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from landing.models import Device, Order, Subscription
from retention.models import BillingRecord, PremiumUsage, email_fingerprint
from retention.usage import mark_premium_used

User = get_user_model()

SECRET = "test-extension-secret"


def _paid_user(email="payer@example.com", uid_suffix="a"):
    user = User.objects.create_user(username=email, email=email, password="x")
    now = timezone.now()
    sub = Subscription.objects.create(
        user=user, plan_key="monthly",
        starts_at=now - timedelta(days=3), ends_at=now + timedelta(days=27),
        source="stripe", stripe_customer_id="cus_TEST" + uid_suffix,
        stripe_subscription_id="sub_TEST" + uid_suffix,
    )
    return user, sub


class PremiumUsageTests(TestCase):
    def test_first_call_creates_a_row(self):
        mark_premium_used(42)
        row = PremiumUsage.objects.get(user_id=42)
        self.assertEqual(row.use_days, 1)
        self.assertEqual(row.first_used_at, row.last_used_at)

    def test_second_call_within_the_window_does_not_write_again(self):
        mark_premium_used(42)
        first = PremiumUsage.objects.get(user_id=42).last_used_at
        mark_premium_used(42)
        self.assertEqual(PremiumUsage.objects.get(user_id=42).last_used_at, first)
        self.assertEqual(PremiumUsage.objects.count(), 1)

    def test_a_new_day_counts_as_another_day_of_use(self):
        mark_premium_used(42)
        row = PremiumUsage.objects.get(user_id=42)
        row.last_used_at = row.last_used_at - timedelta(days=2)
        row.last_used_date = row.last_used_date - timedelta(days=2)
        row.save()
        mark_premium_used(42)
        row.refresh_from_db()
        self.assertEqual(row.use_days, 2)

    def test_garbage_input_is_ignored_silently(self):
        for bad in (None, "", "abc", 0, -1):
            mark_premium_used(bad)
        self.assertEqual(PremiumUsage.objects.count(), 0)


class BillingRecordOnDeleteTests(TestCase):
    def test_paid_account_leaves_a_record_behind(self):
        user, sub = _paid_user()
        Device.objects.create(user=user, client_uuid="dev-1", platform="browser")
        mark_premium_used(user.id)
        uid = user.id

        user.delete()

        self.assertFalse(User.objects.filter(pk=uid).exists())
        self.assertFalse(Subscription.objects.filter(pk=sub.pk).exists())
        rec = BillingRecord.objects.get(user_id_snapshot=uid)
        self.assertEqual(rec.stripe_customer_ids, "cus_TESTa")
        self.assertEqual(rec.stripe_subscription_ids, "sub_TESTa")
        self.assertEqual(rec.device_count, 1)
        self.assertEqual(rec.premium_use_days, 1)
        self.assertEqual(len(rec.subscriptions), 1)
        self.assertEqual(rec.subscriptions[0]["plan"], "monthly")

    def test_the_email_address_itself_is_not_kept(self):
        user, _ = _paid_user(email="Payer@Example.com")
        uid = user.id
        user.delete()
        rec = BillingRecord.objects.get(user_id_snapshot=uid)
        blob = json.dumps([
            rec.email_sha256, rec.stripe_customer_ids, rec.stripe_subscription_ids,
            rec.subscriptions, rec.orders, rec.note,
        ])
        self.assertNotIn("payer@example.com", blob.lower())
        # ...but the person can still be matched, case-insensitively.
        self.assertEqual(rec.email_sha256, email_fingerprint("payer@example.com"))

    def test_free_account_leaves_nothing(self):
        user = User.objects.create_user(username="free@example.com",
                                        email="free@example.com", password="x")
        mark_premium_used(user.id)
        user.delete()
        self.assertEqual(BillingRecord.objects.count(), 0)
        self.assertEqual(PremiumUsage.objects.count(), 0,
                         "a usage row with no FK must be cleaned up explicitly")

    def test_usage_row_is_folded_in_and_removed(self):
        user, _ = _paid_user()
        mark_premium_used(user.id)
        user.delete()
        self.assertEqual(PremiumUsage.objects.count(), 0)
        self.assertEqual(BillingRecord.objects.first().premium_use_days, 1)

    def test_crypto_order_is_preserved(self):
        user = User.objects.create_user(username="c@example.com", email="c@example.com", password="x")
        Order.objects.create(order_id="ORD-1", user=user, plan_key="annual",
                             price_amount="39.99", price_currency="USD",
                             gateway="nowpayments", status="paid",
                             paid_at=timezone.now())
        uid = user.id
        user.delete()
        rec = BillingRecord.objects.get(user_id_snapshot=uid)
        self.assertEqual(rec.orders[0]["order_id"], "ORD-1")
        self.assertIsNotNone(rec.first_paid_at)


class RefundVerdictTests(TestCase):
    def test_unused_after_purchase_is_refundable(self):
        user, _ = _paid_user()
        uid = user.id
        user.delete()
        rec = BillingRecord.objects.get(user_id_snapshot=uid)
        self.assertFalse(rec.used_after_purchase)
        self.assertIn("UNUSED", rec.refund_verdict)

    def test_used_after_purchase_is_not_refundable(self):
        user, _ = _paid_user()
        mark_premium_used(user.id)
        uid = user.id
        user.delete()
        rec = BillingRecord.objects.get(user_id_snapshot=uid)
        self.assertTrue(rec.used_after_purchase)
        self.assertIn("USED", rec.refund_verdict)

    def test_use_before_the_payment_does_not_count_as_use(self):
        """A trial-era connection must not block a refund on a later purchase."""
        user, sub = _paid_user()
        mark_premium_used(user.id)
        stale = timezone.now() - timedelta(days=30)
        PremiumUsage.objects.filter(user_id=user.id).update(
            first_used_at=stale, last_used_at=stale)
        uid = user.id
        user.delete()
        rec = BillingRecord.objects.get(user_id_snapshot=uid)
        self.assertFalse(rec.used_after_purchase)


@override_settings(EXTENSION_SHARED_SECRET=SECRET)
class EntitlementStampsUsageTests(TestCase):
    """The pool asking "is this device premium?" is the moment premium is served."""

    def _post(self, device_id):
        sig = hmac.new(SECRET.encode(), device_id.encode(), hashlib.sha256).hexdigest()
        return self.client.post(reverse("extension_entitlement"),
                                data=json.dumps({"device_id": device_id}),
                                content_type="application/json",
                                HTTP_X_POOL_SIG=sig)

    def test_premium_answer_records_the_use(self):
        user, _ = _paid_user()
        Device.objects.create(user=user, client_uuid="dev-9", platform="browser", is_active=True)
        resp = self._post("dev-9")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["premium"])
        self.assertTrue(PremiumUsage.objects.filter(user_id=user.id).exists())

    def test_non_premium_answer_records_nothing(self):
        user = User.objects.create_user(username="f@example.com", email="f@example.com", password="x")
        Device.objects.create(user=user, client_uuid="dev-8", platform="browser", is_active=True)
        resp = self._post("dev-8")
        self.assertFalse(resp.json()["premium"])
        self.assertEqual(PremiumUsage.objects.count(), 0)

    def test_rejected_request_records_nothing(self):
        user, _ = _paid_user()
        Device.objects.create(user=user, client_uuid="dev-7", platform="browser", is_active=True)
        resp = self.client.post(reverse("extension_entitlement"),
                                data=json.dumps({"device_id": "dev-7"}),
                                content_type="application/json",
                                HTTP_X_POOL_SIG="wrong")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(PremiumUsage.objects.count(), 0)


class SharedCacheTests(TestCase):
    """The rate limiters are only as good as the cache behind them.

    LocMemCache is per-process, so with several gunicorn workers the checkout
    brake multiplied by the worker count and reset on every deploy. That is not
    hypothetical: the brake shipped 2026-09-10 and one account still pushed 9
    cards through in 9 minutes on 2026-09-17.
    """

    def test_cache_backend_is_shared_across_processes(self):
        backend = settings.CACHES["default"]["BACKEND"]
        self.assertNotIn("locmem", backend.lower(),
                         "a per-process cache silently disables every rate limit")
        self.assertIn("db.DatabaseCache", backend)

    def test_the_cache_table_actually_exists(self):
        cache.set("retention-probe", "v", 30)
        self.assertEqual(cache.get("retention-probe"), "v")

    def test_incr_works_on_this_backend(self):
        """Both rate limiters are get_or_set + incr; incr must not raise here."""
        cache.delete("retention-counter")
        cache.get_or_set("retention-counter", 0, 60)
        self.assertEqual(cache.incr("retention-counter"), 1)
        self.assertEqual(cache.incr("retention-counter"), 2)


class CheckoutThrottleTests(TestCase):
    """End-to-end on the real brake, with the real cache backend."""

    def test_user_is_stopped_at_the_cap(self):
        from landing.views import _CHECKOUT_MAX_PER_USER_H, _checkout_throttled

        user = User.objects.create_user(username="t@example.com", email="t@example.com", password="x")
        req = type("R", (), {})()
        req.user = user
        req.META = {"REMOTE_ADDR": "203.0.113.9"}

        allowed = 0
        for _ in range(_CHECKOUT_MAX_PER_USER_H + 3):
            if _checkout_throttled(req):
                break
            allowed += 1
        self.assertEqual(allowed, _CHECKOUT_MAX_PER_USER_H,
                         "the card-testing brake must stop exactly at the cap")
