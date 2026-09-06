# landing/management/commands/reconcile_payments.py
# Ödeme mutabakatı — sunucu crontab'ı için giriş noktası.
# Aynı mantığı HTTP üzerinden /api/cron/reconcile/ da çalıştırır (cron-job.org).
from django.core.management.base import BaseCommand

from landing.helpers.reconcile import run_reconcile


class Command(BaseCommand):
    help = "NOWPayments pending siparişlerini ve Stripe aboneliklerini senkronlar."

    def handle(self, *args, **opts):
        stats = run_reconcile(np_limit=200, stripe_limit=500)
        self.stdout.write(
            f"NOWPayments: {stats['np_checked']} kontrol, {stats['np_paid']} ödendi, "
            f"{stats['np_failed']} düştü | Stripe: {stats['stripe_synced']} senkron, "
            f"{stats['stripe_extended']} uzatıldı | nonce temizliği: {stats['links_purged']}"
        )
        for e in stats["errors"]:
            self.stderr.write(f"  HATA: {e}")
