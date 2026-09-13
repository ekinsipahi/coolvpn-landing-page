"""Admin panelinin gercekten acildigini ve kullanici sayfasinin dogru
ozeti gosterdigini dogrular.

Admin sayfalari test edilmeyince sessizce bozulur: bir alan adi degisir,
sayfa 500 verir ve bunu ancak panele girince fark edersin.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from landing.models import Device, Order, Subscription, SupportTicket

User = get_user_model()


class AdminBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = User.objects.create_superuser(
            username="patron", email="patron@vpnsterr.test", password="Pa55!wordAdmin")
        cls.premium = User.objects.create_user(
            username="premiumcu", email="premium@vpnsterr.test", password="x")
        now = timezone.now()
        cls.sub = Subscription.objects.create(
            user=cls.premium, plan_key="annual", starts_at=now,
            ends_at=now + timedelta(days=300), source="stripe",
            stripe_customer_id="cus_TEST123", stripe_subscription_id="sub_TEST123")
        # (user, client_uuid) benzersiz: ikisine de ayri client_uuid sart.
        Device.objects.create(user=cls.premium, platform="browser", name="Chrome",
                              client_uuid="dev-chrome", is_active=True, last_seen=now)
        Device.objects.create(user=cls.premium, platform="android", name="Pixel",
                              client_uuid="dev-pixel", is_active=False)
        cls.free = User.objects.create_user(
            username="bedavaci", email="free@vpnsterr.test", password="x")
        cls.expired = User.objects.create_user(
            username="bitmis", email="bitmis@vpnsterr.test", password="x")
        Subscription.objects.create(
            user=cls.expired, plan_key="monthly", starts_at=now - timedelta(days=60),
            ends_at=now - timedelta(days=30), source="crypto")
        SupportTicket.objects.create(user=cls.premium, ref="TCK-1", subject="yardım",
                                     status=SupportTicket.STATUS_OPEN)

    def setUp(self):
        self.client.force_login(self.boss)


class DashboardTests(AdminBaseTests):
    def test_index_renders_with_metrics(self):
        r = self.client.get(reverse("admin:index"))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        for label in ("Premium", "Açık destek", "Son 30 günün tahsilatı",
                      "Aktif abonelikler — ödeme kaynağı", "Son kayıt olanlar"):
            with self.subTest(label=label):
                self.assertIn(label, body)

    def test_index_still_lists_the_apps(self):
        # Ozet panel eklerken Django'nun uygulama listesini kaybetmis olmayalim.
        body = self.client.get(reverse("admin:index")).content.decode()
        self.assertIn("Subscriptions", body)
        self.assertIn("Devices", body)

    def test_branding_is_ours(self):
        self.assertIn("VPNsterr", self.client.get(reverse("admin:index")).content.decode())

    def test_no_unrendered_tags(self):
        body = self.client.get(reverse("admin:index")).content.decode()
        self.assertNotIn("{%", body)
        self.assertNotIn("{{", body)


class UserAdminTests(AdminBaseTests):
    def test_changelist_shows_plan_and_devices(self):
        r = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("PREMIUM", body)
        self.assertIn("Free", body)
        self.assertIn("Otomatik yenilenir", body)   # stripe rozeti
        self.assertIn("1 aktif / 2 toplam", body)   # cihaz sayaci

    def test_change_page_summary(self):
        r = self.client.get(reverse("admin:auth_user_change", args=[self.premium.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("Özet", body)
        self.assertIn("cus_TEST123", body)          # Stripe musteri linki
        self.assertIn("dashboard.stripe.com", body)
        self.assertIn("Stripe tarafından yönetiliyor", body)  # drift uyarisi
        for inline in ("Abonelikler", "Cihazlar", "Siparişler", "Destek talepleri"):
            with self.subTest(inline=inline):
                self.assertIn(inline, body)

    def test_free_user_page_has_no_stripe_warning(self):
        body = self.client.get(
            reverse("admin:auth_user_change", args=[self.free.pk])).content.decode()
        self.assertNotIn("Stripe tarafından yönetiliyor", body)

    def test_premium_filter(self):
        url = reverse("admin:auth_user_changelist")
        prem = self.client.get(url, {"vpn_plan": "premium"}).context["cl"].queryset
        self.assertEqual([u.pk for u in prem], [self.premium.pk])
        free = self.client.get(url, {"vpn_plan": "free"}).context["cl"].queryset
        self.assertIn(self.free.pk, [u.pk for u in free])
        self.assertNotIn(self.expired.pk, [u.pk for u in free])
        exp = self.client.get(url, {"vpn_plan": "expired"}).context["cl"].queryset
        self.assertEqual([u.pk for u in exp], [self.expired.pk])

    def test_source_filter(self):
        qs = self.client.get(reverse("admin:auth_user_changelist"),
                             {"vpn_source": "stripe"}).context["cl"].queryset
        self.assertEqual([u.pk for u in qs], [self.premium.pk])

    def test_changelist_does_not_scale_queries_with_users(self):
        """N+1 bekcisi.

        Sayimlar annotate ile tek sorguda geliyor; 40 kullanici daha
        eklemek sorgu sayisini artirmamali. Bu test olmadan, bir gun
        biri annotate'i kaldirir ve panel 500 kullanicida acilmaz olur.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        url = reverse("admin:auth_user_changelist")
        self.client.get(url)  # onbellekleri isit
        with CaptureQueriesContext(connection) as first:
            self.client.get(url)
        before = len(first)

        now = timezone.now()
        for i in range(40):
            u = User.objects.create_user(username=f"yigin{i}", email=f"y{i}@t.test", password="x")
            Subscription.objects.create(user=u, plan_key="monthly", starts_at=now,
                                        ends_at=now + timedelta(days=10), source="crypto")
            Device.objects.create(user=u, platform="browser", client_uuid=f"yigin-{i}",
                                  is_active=True, last_seen=now)
        with CaptureQueriesContext(connection) as second:
            self.client.get(url)
        after = len(second)
        self.assertLessEqual(after, before + 2,
                             f"kullanici artinca sorgu sayisi patladi: {before} -> {after}")


class AdminActionTests(AdminBaseTests):
    def _run(self, action, users):
        return self.client.post(reverse("admin:auth_user_changelist"), {
            "action": action, "_selected_action": [str(u.pk) for u in users],
        }, follow=True)

    def test_grant_one_year(self):
        r = self._run("ver_1_yil", [self.free])
        self.assertEqual(r.status_code, 200)
        sub = Subscription.objects.filter(user=self.free).first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.source, "manual")
        self.assertEqual(sub.plan_key, "annual")
        self.assertGreater(sub.ends_at, timezone.now() + timedelta(days=364))

    def test_grant_stacks_on_top_of_an_active_plan(self):
        # Suresi olan birine sure eklemek, kalan gunleri YAKMAMALI.
        old_end = self.sub.ends_at
        self._run("ver_1_ay", [self.premium])
        newest = Subscription.objects.filter(user=self.premium).order_by("-ends_at").first()
        self.assertEqual(newest.starts_at, old_end)
        self.assertEqual(newest.ends_at, old_end + timedelta(days=30))

    def test_end_premium_warns_when_stripe_keeps_charging(self):
        r = self._run("premiumu_bitir", [self.premium])
        self.sub.refresh_from_db()
        self.assertLessEqual(self.sub.ends_at, timezone.now())
        msgs = " ".join(str(m) for m in r.context["messages"])
        self.assertIn("Stripe", msgs)
        self.assertIn("DEVAM EDER", msgs)

    def test_deactivate_devices(self):
        self._run("cihazlari_kapat", [self.premium])
        self.assertEqual(Device.objects.filter(user=self.premium, is_active=True).count(), 0)


class OtherAdminPagesTests(AdminBaseTests):
    def test_every_registered_changelist_opens(self):
        """Admin'e kayitli her modelin liste sayfasi acilmali.

        Tablosu HENUZ olmayan modeller atlanir: baska bir ajan modeli
        yazmis ama migration'i daha uretmemis olabilir; o onun isi,
        burada patlatmak yanlis alarm olur. Atlananlar yine de yazilir.
        """
        from django.contrib import admin as dj_admin
        from django.db import connection

        tables = set(connection.introspection.table_names())
        broken, skipped = [], []
        for model in dj_admin.site._registry:
            if model._meta.db_table not in tables:
                skipped.append(model._meta.label)
                continue
            url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
            code = self.client.get(url).status_code
            if code != 200:
                broken.append(f"{model._meta.label}={code}")
        if skipped:
            print(f"\n  (tablosu olmayan, atlanan modeller: {', '.join(sorted(skipped))})")
        self.assertEqual(broken, [], f"acilmayan changelist: {broken}")
