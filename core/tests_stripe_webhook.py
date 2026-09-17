"""Stripe webhook'u ve abonelik verme mantigi.

NEDEN VAR: 2026-09-16'da bir musteri iki kez odedi ve premium HIC verilmedi.
Webhook 500 veriyordu; ne abonelik aciliyordu ne bildirim maili gidiyordu ve
disaridan hicbir belirti yoktu -- Stripe "teslim edilemedi" diyordu, biz de
bakmiyorduk.

Testler GERCEK StripeObject uretir (convert_to_stripe_object). Duz dict ile
yazilsalardi hatanin hicbiri tekrar etmezdi: sorun tam olarak StripeObject'in
artik dict GIBI davranmamasiydi.
"""
import json
from datetime import datetime, timezone as dt_tz
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from stripe._util import convert_to_stripe_object as to_stripe

from landing.helpers.stripe_gw import (amount_label, invoice_subscription_id,
                                       sfield, subscription_period)
from landing.models import Subscription

User = get_user_model()

P_START = 1789579715   # 16.09.2026
P_END = 1792171715     # 16.10.2026


def new_subscription(sub_id="sub_TEST", customer="cus_TEST",
                     start=P_START, end=P_END, cents=499):
    """Yeni API bicimi: donem alanlari KALEMDE, ust seviyede yok."""
    return to_stripe({
        "object": "subscription", "id": sub_id, "customer": customer,
        "status": "active",
        "items": {"object": "list", "data": [{
            "object": "subscription_item", "id": "si_TEST",
            "current_period_start": start, "current_period_end": end,
            "price": {"object": "price", "unit_amount": cents, "currency": "usd"},
        }]},
    })


def old_subscription(sub_id="sub_OLD", start=P_START, end=P_END):
    """Eski bicim: donem alanlari ust seviyede."""
    return to_stripe({
        "object": "subscription", "id": sub_id, "customer": "cus_OLD",
        "current_period_start": start, "current_period_end": end,
        "items": {"object": "list", "data": []},
    })


class StripeObjectIsNotADictTests(TestCase):
    """Hatanin kendisi: bu nesnelerde .get() YOK."""

    def test_stripe_object_really_rejects_get(self):
        sess = to_stripe({"object": "checkout.session", "id": "cs_1",
                          "subscription": "sub_1"})
        with self.assertRaises(AttributeError):
            sess.get("subscription")

    def test_sfield_reads_it_anyway(self):
        sess = to_stripe({"object": "checkout.session", "id": "cs_1",
                          "subscription": "sub_1",
                          "metadata": {"user_id": "7", "plan_key": "annual"}})
        self.assertEqual(sfield(sess, "subscription"), "sub_1")
        self.assertEqual(sfield(sess, "metadata", "user_id"), "7")
        self.assertEqual(sfield(sess, "metadata", "yok", default="x"), "x")
        self.assertIsNone(sfield(sess, "hic", "boyle", "sey"))

    def test_sfield_works_on_plain_dicts_too(self):
        self.assertEqual(sfield({"a": {"b": 1}}, "a", "b"), 1)
        self.assertEqual(sfield({"a": {}}, "a", "b", default=9), 9)

    def test_sfield_indexes_lists(self):
        self.assertEqual(sfield({"d": [{"k": "v"}]}, "d", 0, "k"), "v")
        self.assertIsNone(sfield({"d": []}, "d", 0, "k"))


class PeriodAndInvoiceShapeTests(TestCase):
    def test_period_comes_from_the_item_in_the_new_shape(self):
        self.assertEqual(subscription_period(new_subscription()), (P_START, P_END))

    def test_period_still_read_from_top_level_in_the_old_shape(self):
        self.assertEqual(subscription_period(old_subscription()), (P_START, P_END))

    def test_invoice_subscription_from_parent(self):
        inv = to_stripe({"object": "invoice", "id": "in_1", "parent": {
            "type": "subscription_details",
            "subscription_details": {"subscription": "sub_9"}}})
        self.assertEqual(invoice_subscription_id(inv), "sub_9")

    def test_invoice_subscription_from_top_level_old_shape(self):
        inv = to_stripe({"object": "invoice", "id": "in_1", "subscription": "sub_8"})
        self.assertEqual(invoice_subscription_id(inv), "sub_8")

    def test_amount_label(self):
        self.assertEqual(amount_label(new_subscription(cents=499)), "4.99 USD")
        self.assertEqual(amount_label(old_subscription()), "")


class MailCapture:
    """send_email_bg daemon thread aciyor; testte senkron yakala."""

    def __enter__(self):
        from landing.helpers import mailer
        self.sent = []
        self._orig = mailer.send_email_bg
        mailer.send_email_bg = lambda to, subject, html, text="", reply_to="": \
            self.sent.append((to, subject))
        return self

    def __exit__(self, *a):
        from landing.helpers import mailer
        mailer.send_email_bg = self._orig


class GrantSubscriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="odeyen", email="o@t.test",
                                             password="x")

    def test_new_shape_subscription_is_granted(self):
        from landing.views import _grant_stripe_subscription
        with MailCapture() as mc:
            local = _grant_stripe_subscription(self.user, "monthly", new_subscription())
        self.assertEqual(local.source, "stripe")
        self.assertEqual(local.stripe_subscription_id, "sub_TEST")
        self.assertEqual(local.stripe_customer_id, "cus_TEST")
        self.assertEqual(local.ends_at, datetime.fromtimestamp(P_END, dt_tz.utc))
        # Hem musteriye hem sahibe mail: bu akis sessizce kaybolmasin.
        self.assertEqual(len(mc.sent), 2)

    def test_renewal_extends_but_never_shrinks(self):
        """Mükerrer ödeme telafisi ya da elle jest, yenilemede SILINMEMELI."""
        from landing.views import _grant_stripe_subscription
        with MailCapture():
            local = _grant_stripe_subscription(self.user, "monthly", new_subscription())
        far = datetime.fromtimestamp(P_END + 30 * 86400, dt_tz.utc)
        Subscription.objects.filter(pk=local.pk).update(ends_at=far)

        with MailCapture():
            again = _grant_stripe_subscription(self.user, "monthly", new_subscription())
        self.assertEqual(again.ends_at, far, "yenileme senkronu süreyi geri aldı")

        later = P_END + 60 * 86400
        with MailCapture():
            grown = _grant_stripe_subscription(
                self.user, "monthly", new_subscription(start=P_END, end=later))
        self.assertEqual(grown.ends_at, datetime.fromtimestamp(later, dt_tz.utc))

    def test_missing_period_raises_instead_of_silently_wrong_dates(self):
        from landing.views import _grant_stripe_subscription
        broken = to_stripe({"object": "subscription", "id": "sub_X",
                            "customer": "cus_X",
                            "items": {"object": "list", "data": [{}]}})
        with self.assertRaises(ValueError):
            _grant_stripe_subscription(self.user, "monthly", broken)


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
class WebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="webhookcu",
                                             email="w@t.test", password="x")

    def _post(self, event_dict, subscription=None):
        api = mock.MagicMock()
        api.Webhook.construct_event.return_value = to_stripe(event_dict)
        api.Subscription.retrieve.return_value = subscription
        with mock.patch("landing.views._stripe", return_value=api), \
             mock.patch("landing.views.stripe_enabled", return_value=True), \
             MailCapture() as mc:
            r = self.client.post("/api/payment/stripe/webhook/", data=b"{}",
                                 content_type="application/json",
                                 HTTP_STRIPE_SIGNATURE="t=1,v1=x")
        return r, mc

    def test_checkout_completed_grants_premium(self):
        sub = new_subscription(sub_id="sub_CO", customer="cus_CO")
        r, mc = self._post({
            "object": "event", "id": "evt_1", "type": "checkout.session.completed",
            "data": {"object": {
                "object": "checkout.session", "id": "cs_1", "subscription": "sub_CO",
                "payment_status": "paid",
                "metadata": {"user_id": str(self.user.id), "plan_key": "monthly"}}},
        }, subscription=sub)
        self.assertEqual(r.status_code, 200)
        local = Subscription.objects.filter(user=self.user).first()
        self.assertIsNotNone(local, "webhook 200 döndü ama abonelik açılmadı")
        self.assertEqual(local.stripe_subscription_id, "sub_CO")
        self.assertEqual(len(mc.sent), 2)

    def test_invoice_paid_new_shape_extends(self):
        Subscription.objects.create(
            user=self.user, plan_key="monthly", source="stripe",
            starts_at=datetime.fromtimestamp(P_START - 86400, dt_tz.utc),
            ends_at=datetime.fromtimestamp(P_START, dt_tz.utc),
            stripe_subscription_id="sub_IN", stripe_customer_id="cus_IN")
        r, _ = self._post({
            "object": "event", "id": "evt_2", "type": "invoice.paid",
            "data": {"object": {
                "object": "invoice", "id": "in_1",
                "parent": {"type": "subscription_details",
                           "subscription_details": {"subscription": "sub_IN"}}}},
        }, subscription=new_subscription(sub_id="sub_IN", customer="cus_IN"))
        self.assertEqual(r.status_code, 200)
        local = Subscription.objects.get(stripe_subscription_id="sub_IN")
        self.assertEqual(local.ends_at, datetime.fromtimestamp(P_END, dt_tz.utc))

    def test_unknown_user_does_not_crash(self):
        r, _ = self._post({
            "object": "event", "id": "evt_3", "type": "checkout.session.completed",
            "data": {"object": {"object": "checkout.session", "id": "cs_2",
                                "subscription": "sub_Z",
                                "metadata": {"user_id": "999999"}}},
        }, subscription=new_subscription())
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Subscription.objects.exists())


# Turnstile bu sınıfın konusu değil; .env'de anahtar varsa checkout'u
# 403'lerdi ve testler geliştiricinin ortamına göre farklı sonuç verirdi.
# Açıkça kapatmak testi deterministik yapar (captcha'nın kendi testleri
# core/tests_bot_shield.py'de).
@override_settings(TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="")
class DoubleBillingGuardTests(TestCase):
    """Aynı kişiden ikinci kez tahsilat açılmamalı.

    Gerçek olay: müşteri iki checkout tamamladı, iki ayrı Stripe müşterisi ve
    iki canlı abonelik oluştu, kartından iki kez çekildi.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="iki", email="iki@t.test",
                                             password="x")
        self.client.force_login(self.user)

    def _create(self, api):
        with mock.patch("landing.views._stripe", return_value=api), \
             mock.patch("landing.views.stripe_enabled", return_value=True), \
             mock.patch("landing.views.ensure_price", return_value="price_1"), \
             mock.patch("landing.views.get_or_create_customer", return_value="cus_1"):
            return self.client.post("/api/checkout/stripe/",
                                    data='{"plan":"monthly"}',
                                    content_type="application/json")

    def _api(self, statuses=()):
        api = mock.MagicMock()
        api.Subscription.list.return_value = mock.MagicMock(data=[
            to_stripe({"object": "subscription", "id": f"sub_{i}", "status": st})
            for i, st in enumerate(statuses)])
        api.checkout.Session.create.return_value = mock.MagicMock(
            url="https://checkout.stripe.test/s")
        return api

    def test_blocked_when_a_local_stripe_subscription_is_active(self):
        Subscription.objects.create(
            user=self.user, plan_key="monthly", source="stripe",
            starts_at=datetime.fromtimestamp(P_START, dt_tz.utc),
            ends_at=datetime.fromtimestamp(P_END, dt_tz.utc),
            stripe_subscription_id="sub_A", stripe_customer_id="cus_A")
        api = self._api()
        r = self._create(api)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "already_subscribed")
        api.checkout.Session.create.assert_not_called()

    def test_blocked_when_stripe_has_one_even_if_local_row_is_missing(self):
        """Asıl senaryo: webhook bozuk olduğu için yerel kayıt HİÇ yok."""
        self.assertFalse(Subscription.objects.exists())
        api = self._api(statuses=["active"])
        r = self._create(api)
        self.assertEqual(r.status_code, 409)
        api.checkout.Session.create.assert_not_called()

    def test_allowed_when_there_is_no_subscription_anywhere(self):
        api = self._api()
        r = self._create(api)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        api.checkout.Session.create.assert_called_once()

    def test_a_cancelled_stripe_subscription_does_not_block(self):
        """İptal edilmiş abonelik yeni satışı engellememeli."""
        r = self._create(self._api(statuses=["canceled", "incomplete_expired"]))
        self.assertEqual(r.status_code, 200)

    def test_trialing_also_blocks(self):
        r = self._create(self._api(statuses=["trialing"]))
        self.assertEqual(r.status_code, 409)

    def test_expired_local_subscription_does_not_block_a_new_one(self):
        Subscription.objects.create(
            user=self.user, plan_key="monthly", source="stripe",
            starts_at=datetime.fromtimestamp(P_START - 60 * 86400, dt_tz.utc),
            ends_at=datetime.fromtimestamp(P_START - 30 * 86400, dt_tz.utc),
            stripe_subscription_id="sub_OLD", stripe_customer_id="cus_OLD")
        r = self._create(self._api(statuses=["canceled"]))
        self.assertEqual(r.status_code, 200)


class ReconcileStripeTests(TestCase):
    """Cron da aynı .get() hatasıyla her turda düşüyordu."""

    def test_reconcile_extends_with_the_new_subscription_shape(self):
        from landing.helpers import reconcile as rec

        user = User.objects.create_user(username="cron", email="c@t.test", password="x")
        local = Subscription.objects.create(
            user=user, plan_key="monthly", source="stripe",
            starts_at=datetime.fromtimestamp(P_START, dt_tz.utc),
            ends_at=datetime.fromtimestamp(P_START, dt_tz.utc),
            stripe_subscription_id="sub_R", stripe_customer_id="cus_R")

        api = mock.MagicMock()
        api.Subscription.retrieve.return_value = new_subscription(sub_id="sub_R")
        with mock.patch("landing.helpers.stripe_gw._api", return_value=api), \
             mock.patch("landing.helpers.stripe_gw.stripe_enabled", return_value=True):
            out = rec.run_reconcile()

        local.refresh_from_db()
        self.assertEqual(local.ends_at, datetime.fromtimestamp(P_END, dt_tz.utc))
        self.assertEqual(out["stripe_extended"], 1)
        self.assertEqual([e for e in out["errors"] if "stripe" in e], [])


class CustomerSelectionTests(TestCase):
    """Aynı kullanıcı için birden fazla Stripe müşterisi bulunabilir.

    16.09'da tam bu oldu: webhook bozuk olduğu için yerel kayıt oluşmadı ve
    her ödemede yeni bir müşteri açıldı. Arama ikisini birden döndürünce
    yanlışını seçmek, iptal edilmiş/boş bir müşteriye abonelik açmak demek.
    Stripe'ın arama indeksi de nihai tutarlı — eski kayıt bir süre görünür.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="cok", email="cok@t.test",
                                             password="x")

    def _api(self, customers, subs_by_customer):
        api = mock.MagicMock()
        api.Customer.search.return_value = mock.MagicMock(data=[
            to_stripe({"object": "customer", "id": cid, "created": created})
            for cid, created in customers])
        api.Subscription.list.side_effect = lambda customer, **kw: mock.MagicMock(
            data=[to_stripe({"object": "subscription", "id": f"s_{customer}",
                             "status": st})
                  for st in subs_by_customer.get(customer, [])])
        api.Customer.create.return_value = mock.MagicMock(id="cus_NEW")
        return api

    def _pick(self, api):
        from landing.helpers import stripe_gw
        with mock.patch.object(stripe_gw, "_api", return_value=api):
            return stripe_gw.get_or_create_customer(self.user)

    def test_prefers_the_customer_with_a_live_subscription(self):
        api = self._api([("cus_OLD", 100), ("cus_LIVE", 50)],
                        {"cus_OLD": ["canceled"], "cus_LIVE": ["active"]})
        self.assertEqual(self._pick(api), "cus_LIVE")
        api.Customer.create.assert_not_called()

    def test_falls_back_to_the_newest_when_none_are_live(self):
        api = self._api([("cus_A", 100), ("cus_B", 900)],
                        {"cus_A": ["canceled"], "cus_B": ["canceled"]})
        self.assertEqual(self._pick(api), "cus_B")
        api.Customer.create.assert_not_called()

    def test_creates_one_when_nothing_matches(self):
        api = self._api([], {})
        self.assertEqual(self._pick(api), "cus_NEW")
        api.Customer.create.assert_called_once()

    def test_local_record_still_wins_and_costs_no_api_call(self):
        # Yerel kayıt varsa Stripe'a hiç gitmemeli: en sık yol bu.
        Subscription.objects.create(
            user=self.user, plan_key="monthly", source="stripe",
            starts_at=datetime.fromtimestamp(P_START, dt_tz.utc),
            ends_at=datetime.fromtimestamp(P_END, dt_tz.utc),
            stripe_subscription_id="sub_L", stripe_customer_id="cus_LOCAL")
        api = self._api([("cus_OTHER", 1)], {})
        self.assertEqual(self._pick(api), "cus_LOCAL")
        api.Customer.search.assert_not_called()


class WebhookReplayGuardTests(TestCase):
    """Stripe başarısız event'leri YENİDEN GÖNDERİR.

    16.09'da webhook düzelince Stripe eski denemeleri tekrar yolladı: iptal
    edilmiş bir abonelik için yeni yerel kayıt açıldı, müşteriye ikinci kez
    "premium aktif" maili gitti ve ölü müşteri kimliği hesabın en güncel
    kaydı oldu (sonraki ödemede yanlış müşteri seçilirdi).
    """

    def setUp(self):
        self.user = User.objects.create_user(username="tekrar", email="t@t.test",
                                             password="x")

    def _sub(self, status, sub_id="sub_DEAD"):
        d = new_subscription(sub_id=sub_id).to_dict()
        d["status"] = status
        return to_stripe(d)

    def test_cancelled_subscription_does_not_create_a_row_or_mail(self):
        from landing.views import _grant_stripe_subscription
        with MailCapture() as mc:
            out = _grant_stripe_subscription(self.user, "monthly", self._sub("canceled"))
        self.assertIsNone(out)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())
        self.assertEqual(mc.sent, [], "iptal edilmiş abonelik için mail gitti")

    def test_incomplete_expired_is_also_ignored(self):
        from landing.views import _grant_stripe_subscription
        with MailCapture():
            self.assertIsNone(_grant_stripe_subscription(
                self.user, "monthly", self._sub("incomplete_expired")))
        self.assertFalse(Subscription.objects.exists())

    def test_an_existing_row_is_still_synced_even_if_now_cancelled(self):
        """Var olan kaydın tarihi senkronlanmalı; engellenen sadece YENİ kayıt."""
        from landing.views import _grant_stripe_subscription
        local = Subscription.objects.create(
            user=self.user, plan_key="monthly", source="stripe",
            starts_at=datetime.fromtimestamp(P_START, dt_tz.utc),
            ends_at=datetime.fromtimestamp(P_START, dt_tz.utc),
            stripe_subscription_id="sub_DEAD", stripe_customer_id="cus_D")
        with MailCapture():
            out = _grant_stripe_subscription(self.user, "monthly", self._sub("canceled"))
        self.assertEqual(out.pk, local.pk)
        out.refresh_from_db()
        self.assertEqual(out.ends_at, datetime.fromtimestamp(P_END, dt_tz.utc))

    def test_active_subscription_still_creates_a_row(self):
        from landing.views import _grant_stripe_subscription
        with MailCapture() as mc:
            out = _grant_stripe_subscription(self.user, "monthly", self._sub("active", "sub_OK"))
        self.assertIsNotNone(out)
        self.assertEqual(len(mc.sent), 2)


class OneClickCancelTests(TestCase):
    """Dashboard'dan tek tıkla iptal / geri alma."""

    def setUp(self):
        self.user = User.objects.create_user(username="iptalci", email="i@t.test",
                                             password="x")
        self.client.force_login(self.user)
        self.local = Subscription.objects.create(
            user=self.user, plan_key="monthly", source="stripe",
            starts_at=datetime.fromtimestamp(P_START, dt_tz.utc),
            ends_at=datetime.fromtimestamp(P_END, dt_tz.utc),
            stripe_subscription_id="sub_C", stripe_customer_id="cus_C")

    def _api(self, cancel_at_period_end=False, status="active"):
        api = mock.MagicMock()
        obj = to_stripe({"object": "subscription", "id": "sub_C", "status": status,
                         "cancel_at_period_end": cancel_at_period_end})
        api.Subscription.retrieve.return_value = obj
        api.Subscription.modify.return_value = obj
        return api

    def _call(self, url, api, payload=None):
        with mock.patch("landing.views._stripe", return_value=api), \
             mock.patch("landing.views.stripe_enabled", return_value=True):
            if payload is None:
                return self.client.get(url)
            return self.client.post(url, data=json.dumps(payload),
                                    content_type="application/json")

    def test_status_reports_the_live_state(self):
        r = self._call(reverse("stripe_billing_status"), self._api(cancel_at_period_end=True))
        j = r.json()
        self.assertTrue(j["has_subscription"])
        self.assertTrue(j["cancel_at_period_end"])

    def test_cancel_sets_cancel_at_period_end(self):
        api = self._api(cancel_at_period_end=True)
        r = self._call(reverse("stripe_cancel_subscription"), api, {})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["cancel_at_period_end"])
        # Hemen kesmiyoruz: ödenen günler alınmaz.
        api.Subscription.modify.assert_called_once_with("sub_C", cancel_at_period_end=True)

    def test_resume_undoes_it(self):
        api = self._api(cancel_at_period_end=False)
        r = self._call(reverse("stripe_cancel_subscription"), api, {"resume": True})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["cancel_at_period_end"])
        api.Subscription.modify.assert_called_once_with("sub_C", cancel_at_period_end=False)

    def test_access_until_comes_from_our_record_not_stripe(self):
        # Elle verilmiş ek süre Stripe'ın dönem sonundan ileride olabilir.
        far = datetime.fromtimestamp(P_END + 30 * 86400, dt_tz.utc)
        Subscription.objects.filter(pk=self.local.pk).update(ends_at=far)
        r = self._call(reverse("stripe_cancel_subscription"), self._api(True), {})
        self.assertEqual(r.json()["access_until"][:10], far.date().isoformat())

    def test_without_a_subscription_it_is_404(self):
        Subscription.objects.all().delete()
        r = self._call(reverse("stripe_cancel_subscription"), self._api(), {})
        self.assertEqual(r.status_code, 404)

    def test_stripe_failure_is_reported_not_swallowed(self):
        api = self._api()
        api.Subscription.modify.side_effect = RuntimeError("stripe down")
        r = self._call(reverse("stripe_cancel_subscription"), api, {})
        self.assertEqual(r.status_code, 502)
        self.assertIn("detail", r.json())

    def test_anonymous_cannot_cancel(self):
        self.client.logout()
        r = self.client.post(reverse("stripe_cancel_subscription"),
                             data="{}", content_type="application/json")
        self.assertEqual(r.status_code, 302)

    def test_dashboard_shows_the_cancel_button_for_card_subscribers(self):
        body = self.client.get("/dashboard/").content.decode()
        self.assertIn("Cancel subscription", body)
        self.assertIn("/api/billing/cancel/", body)

    def test_crypto_subscriber_gets_no_cancel_button(self):
        Subscription.objects.all().update(source="crypto", stripe_subscription_id="")
        body = self.client.get("/dashboard/").content.decode()
        self.assertNotIn("Cancel subscription", body)
