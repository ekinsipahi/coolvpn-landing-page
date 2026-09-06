# landing/management/commands/reconcile_payments.py
# Periyodik ödeme mutabakatı — webhook kaçarsa/yokken güvenlik ağı.
#
# Kurulum (sunucuda crontab -e):
#   */15 * * * * cd /path/to/coolvpn-landing-page && /usr/bin/python3 manage.py reconcile_payments >> /var/log/vpnsterr-reconcile.log 2>&1
#
# Ne yapar:
#   1) NOWPayments: son 48 saatin "pending" siparişlerini API'den sorgular;
#      ödenmişse order'ı paid yapar ve aboneliği tanımlar (IPN ile aynı mantık).
#   2) Stripe: yerel stripe abonelikleri Stripe'taki gerçek durumla eşitler —
#      yenilendiyse ends_at'i yeni dönem sonuna uzatır.

from datetime import timedelta

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from landing.helpers.subscription import grant_subscription
from landing.models import Order, Subscription


class Command(BaseCommand):
    help = "NOWPayments pending siparişlerini ve Stripe aboneliklerini senkronlar."

    def handle(self, *args, **opts):
        self.reconcile_nowpayments()
        self.sync_stripe()

    # ---------------- NOWPayments ----------------
    def reconcile_nowpayments(self):
        np_key = getattr(settings, "NOWPAYMENTS_API_KEY", "")
        np_base = getattr(settings, "NOWPAYMENTS_BASE_URL", "https://api.nowpayments.io/v1")
        if not np_key:
            self.stdout.write("NOWPayments: anahtar yok, atlandı.")
            return

        cutoff = timezone.now() - timedelta(hours=48)
        pending = (
            Order.objects
            .filter(status="pending", gateway="nowpayments", created_at__gte=cutoff)
            .exclude(np_invoice_id="")
            .select_related("user")
        )
        checked = paid = failed = 0
        for order in pending:
            checked += 1
            try:
                r = requests.get(
                    f"{np_base}/invoice/{order.np_invoice_id}",
                    headers={"x-api-key": np_key},
                    timeout=15,
                )
                jr = r.json()
            except Exception as e:
                self.stderr.write(f"  NP {order.order_id}: fetch hata {e}")
                continue

            status = (jr.get("payment_status") or jr.get("status") or "").lower()
            order.np_raw = jr
            if status in {"finished", "confirmed"}:
                order.status = "paid"
                order.paid_at = timezone.now()
                order.save(update_fields=["status", "paid_at", "np_raw"])
                grant_subscription(order.user, order.plan_key, order=order)
                paid += 1
                self.stdout.write(f"  NP {order.order_id}: PAID ✓ abonelik tanımlandı")
            elif status in {"failed", "expired", "refunded"}:
                order.status = "failed" if status == "failed" else status
                order.save(update_fields=["status", "np_raw"])
                failed += 1
            else:
                order.save(update_fields=["np_raw"])
        self.stdout.write(f"NOWPayments: {checked} kontrol, {paid} ödendi, {failed} düştü.")

    # ---------------- Stripe ----------------
    def sync_stripe(self):
        from landing.helpers.stripe_gw import stripe_enabled, _api

        if not stripe_enabled():
            self.stdout.write("Stripe: anahtar yok, atlandı.")
            return
        api = _api()

        # Bitişine 40 günden az kalan veya yeni bitmiş stripe abonelikleri eşitle
        window_lo = timezone.now() - timedelta(days=10)
        subs = (
            Subscription.objects
            .filter(source="stripe", ends_at__gte=window_lo)
            .exclude(stripe_subscription_id="")
        )
        synced = extended = 0
        for local in subs:
            try:
                remote = api.Subscription.retrieve(local.stripe_subscription_id)
            except Exception as e:
                self.stderr.write(f"  Stripe {local.stripe_subscription_id}: {e}")
                continue
            synced += 1
            period_end = remote.get("current_period_end")
            if period_end:
                from datetime import datetime, timezone as dt_tz
                new_end = datetime.fromtimestamp(int(period_end), tz=dt_tz.utc)
                if new_end > local.ends_at:
                    local.ends_at = new_end
                    local.save(update_fields=["ends_at"])
                    extended += 1
                    self.stdout.write(f"  Stripe {local.stripe_subscription_id}: uzatıldı → {new_end:%Y-%m-%d}")
        self.stdout.write(f"Stripe: {synced} senkron, {extended} uzatıldı.")
