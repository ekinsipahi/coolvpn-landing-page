"""Fold a user's billing facts into a standalone record just before deletion.

Django's collector sends every ``pre_delete`` signal BEFORE it deletes
anything, so when this receiver runs the user's subscriptions, orders and
devices are all still readable. Same guarantee ``landing.signals`` relies on to
archive assistant messages.

Only accounts that ever paid leave a record behind. Deleting a free account
leaves nothing at all -- keeping billing evidence for someone who never
generated a payment would be retention without a purpose.
"""
import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import BillingRecord, PremiumUsage, email_fingerprint

log = logging.getLogger(__name__)

User = get_user_model()


def _iso(value):
    return value.isoformat() if value else None


@receiver(pre_delete, sender=User, dispatch_uid="retention_billing_record")
def keep_billing_record(sender, instance, **kwargs):
    try:
        _keep(instance)
    except Exception:  # noqa: BLE001 — the user's right to delete does not
        # depend on our bookkeeping succeeding.
        log.exception("retention: billing record failed for user %s", getattr(instance, "pk", "?"))


def _keep(user):
    from landing.models import Device, Order, Subscription

    uid = user.pk
    subs = list(Subscription.objects.filter(user=user).order_by("created_at"))
    orders = list(Order.objects.filter(user=user).order_by("created_at"))
    try:
        from landing.models import PlayPurchase
        plays = list(PlayPurchase.objects.filter(user=user))
    except Exception:  # noqa: BLE001
        plays = []

    paid_orders = [o for o in orders if o.status == "paid"]
    ever_paid = bool(subs or paid_orders or plays)

    usage = PremiumUsage.objects.filter(user_id=uid).first()

    if not ever_paid:
        # Free account: keep nothing, and drop the usage row that has no
        # ForeignKey to cascade it away.
        if usage:
            usage.delete()
        return

    paid_times = [o.paid_at for o in paid_orders if o.paid_at]
    paid_times += [s.starts_at for s in subs if s.starts_at]
    first_paid = min(paid_times) if paid_times else None
    period_ends = [s.ends_at for s in subs if s.ends_at]

    devices = list(Device.objects.filter(user=user))
    device_last_seen = max((d.last_seen for d in devices if d.last_seen), default=None)

    rec = BillingRecord.objects.create(
        user_id_snapshot=uid,
        email_sha256=email_fingerprint(user.email or user.get_username()),
        account_created_at=getattr(user, "date_joined", None),
        account_deleted_at=timezone.now(),
        stripe_customer_ids=" ".join(sorted({s.stripe_customer_id for s in subs if s.stripe_customer_id})),
        stripe_subscription_ids=" ".join(sorted({s.stripe_subscription_id for s in subs if s.stripe_subscription_id})),
        subscriptions=[{
            "plan": s.plan_key, "source": s.source,
            "starts_at": _iso(s.starts_at), "ends_at": _iso(s.ends_at),
            "created_at": _iso(s.created_at),
            "stripe_subscription_id": s.stripe_subscription_id or "",
            "stripe_customer_id": s.stripe_customer_id or "",
        } for s in subs] + [{
            "plan": p.plan_key, "source": "google_play",
            "starts_at": _iso(p.created_at), "ends_at": _iso(p.expires_at),
            "created_at": _iso(p.created_at), "state": p.state,
            "product_id": p.product_id,
        } for p in plays],
        orders=[{
            "order_id": o.order_id, "plan": o.plan_key,
            "amount": str(o.price_amount), "currency": o.price_currency,
            "gateway": o.gateway, "status": o.status,
            "created_at": _iso(o.created_at), "paid_at": _iso(o.paid_at),
        } for o in orders],
        first_paid_at=first_paid,
        last_period_end=max(period_ends) if period_ends else None,
        premium_first_used_at=usage.first_used_at if usage else None,
        premium_last_used_at=usage.last_used_at if usage else None,
        premium_use_days=usage.use_days if usage else 0,
        device_count=len(devices),
        device_last_seen_at=device_last_seen,
    )
    if usage:
        usage.delete()
    log.info("retention: kept billing record %s for deleted user %s (%s)",
             rec.pk, uid, rec.refund_verdict)
