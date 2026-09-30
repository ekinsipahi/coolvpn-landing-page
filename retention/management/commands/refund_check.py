"""Answer "did this person use what they paid for?" for one e-mail address.

Works whether or not the account still exists: a live account is read from the
usage table, a deleted one from the billing record left behind.

    python manage.py refund_check someone@example.com
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from retention.models import BillingRecord, PremiumUsage, email_fingerprint


class Command(BaseCommand):
    help = "Show payment and usage history for an e-mail address (refund eligibility)."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, **opts):
        email = (opts["email"] or "").strip().lower()
        if "@" not in email:
            raise CommandError("give an e-mail address")

        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        found = False

        if user:
            found = True
            self.stdout.write(self.style.MIGRATE_HEADING(f"LIVE ACCOUNT  user_id={user.id}"))
            self.stdout.write(f"  joined      : {user.date_joined}")
            from landing.models import Order, Subscription
            for s in Subscription.objects.filter(user=user).order_by("created_at"):
                self.stdout.write(f"  subscription: {s.plan_key} via {s.source} "
                                  f"{s.starts_at:%Y-%m-%d} → {s.ends_at:%Y-%m-%d} "
                                  f"stripe={s.stripe_subscription_id or '-'}")
            for o in Order.objects.filter(user=user, status="paid").order_by("created_at"):
                self.stdout.write(f"  paid order  : {o.order_id} {o.price_amount} {o.price_currency} at {o.paid_at}")
            u = PremiumUsage.objects.filter(user_id=user.id).first()
            if u:
                self.stdout.write(self.style.WARNING(
                    f"  USED premium: {u.use_days} day(s), first {u.first_used_at}, last {u.last_used_at}"))
                self.stdout.write("  verdict     : USED — not eligible under the unused-service rule")
            else:
                self.stdout.write(self.style.SUCCESS(
                    "  no premium use recorded — eligible for a full refund"))

        for rec in BillingRecord.objects.filter(email_sha256=email_fingerprint(email)):
            found = True
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"DELETED ACCOUNT  user_id={rec.user_id_snapshot}  deleted {rec.account_deleted_at:%Y-%m-%d %H:%M}"))
            self.stdout.write(f"  joined      : {rec.account_created_at}")
            self.stdout.write(f"  first paid  : {rec.first_paid_at}")
            self.stdout.write(f"  stripe cust : {rec.stripe_customer_ids or '-'}")
            self.stdout.write(f"  stripe subs : {rec.stripe_subscription_ids or '-'}")
            for s in rec.subscriptions:
                self.stdout.write(f"  subscription: {s.get('plan')} via {s.get('source')} "
                                  f"{s.get('starts_at')} → {s.get('ends_at')}")
            for o in rec.orders:
                self.stdout.write(f"  order       : {o.get('order_id')} {o.get('amount')} "
                                  f"{o.get('currency')} {o.get('status')}")
            self.stdout.write(f"  devices     : {rec.device_count}, last seen {rec.device_last_seen_at}")
            self.stdout.write(f"  premium use : {rec.premium_use_days} day(s), "
                              f"first {rec.premium_first_used_at}, last {rec.premium_last_used_at}")
            style = self.style.WARNING if rec.used_after_purchase else self.style.SUCCESS
            self.stdout.write(style(f"  verdict     : {rec.refund_verdict}"))

        if not found:
            self.stdout.write("no live account and no retained billing record for that address")
