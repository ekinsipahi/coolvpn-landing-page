# landing/helpers/reconcile.py
# Ödeme mutabakatının TEK kaynağı — hem `manage.py reconcile_payments`
# hem de /api/cron/reconcile/ (cron-job.org) bunu çağırır.

from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from landing.helpers.subscription import grant_subscription
from landing.models import ExtensionLink, Order, Subscription


def run_reconcile(np_limit: int = 25, stripe_limit: int = 50) -> dict:
    """
    Sınırlı iş yapar ki HTTP çağrısı 30 sn timeout'a sığsın; birikmiş kuyruk
    varsa sonraki turlarda erir (5 dk kadansta hızla biter). Idempotent:
    aynı anda iki kez koşsa da çift abonelik doğmaz (grant order-bazlı kilitli).
    """
    out = {"np_checked": 0, "np_paid": 0, "np_failed": 0,
           "stripe_synced": 0, "stripe_extended": 0, "links_purged": 0,
           "errors": []}

    # ---- NOWPayments: bekleyenleri sorgula ----
    np_key = getattr(settings, "NOWPAYMENTS_API_KEY", "")
    np_base = getattr(settings, "NOWPAYMENTS_BASE_URL", "https://api.nowpayments.io/v1")
    if np_key:
        cutoff = timezone.now() - timedelta(hours=48)
        pending = (
            Order.objects
            .filter(status="pending", gateway="nowpayments", created_at__gte=cutoff)
            .exclude(np_invoice_id="")
            .select_related("user")
            .order_by("created_at")[:np_limit]
        )
        for order in pending:
            out["np_checked"] += 1
            try:
                r = requests.get(
                    f"{np_base}/invoice/{order.np_invoice_id}",
                    headers={"x-api-key": np_key},
                    timeout=10,
                )
                jr = r.json()
            except Exception as e:
                out["errors"].append(f"np:{order.order_id}:{e}")
                continue

            status = (jr.get("payment_status") or jr.get("status") or "").lower()
            order.np_raw = jr
            if status in {"finished", "confirmed"}:
                order.status = "paid"
                order.paid_at = timezone.now()
                order.save(update_fields=["status", "paid_at", "np_raw"])
                grant_subscription(order.user, order.plan_key, order=order)
                out["np_paid"] += 1
            elif status in {"failed", "expired", "refunded"}:
                order.status = "failed" if status == "failed" else status
                order.save(update_fields=["status", "np_raw"])
                out["np_failed"] += 1
            else:
                order.save(update_fields=["np_raw"])

    # ---- Stripe: dönem sonu senkronu ----
    from landing.helpers.stripe_gw import stripe_enabled, _api
    if stripe_enabled():
        from datetime import datetime, timezone as dt_tz
        api = _api()
        window_lo = timezone.now() - timedelta(days=10)
        subs = (
            Subscription.objects
            .filter(source="stripe", ends_at__gte=window_lo)
            .exclude(stripe_subscription_id="")
            .order_by("ends_at")[:stripe_limit]
        )
        for local in subs:
            try:
                remote = api.Subscription.retrieve(local.stripe_subscription_id)
            except Exception as e:
                out["errors"].append(f"stripe:{local.stripe_subscription_id}:{e}")
                continue
            out["stripe_synced"] += 1
            period_end = remote.get("current_period_end")
            if period_end:
                new_end = datetime.fromtimestamp(int(period_end), tz=dt_tz.utc)
                if new_end > local.ends_at:
                    local.ends_at = new_end
                    local.save(update_fields=["ends_at"])
                    out["stripe_extended"] += 1

    # ---- Bayat bağlama nonce'ları ----
    cutoff = timezone.now() - timedelta(hours=24)
    n, _ = ExtensionLink.objects.filter(claimed=False, created_at__lt=cutoff).delete()
    out["links_purged"] = n

    # ---- Bayat ANONİM asistan konuşmaları (kayıtsız ziyaretçi; 7 günden
    # eski olanlar silinir ki spam/bot açtığı satırlar süresiz birikmesin.
    # Girişli kullanıcının konuşmaları kalır — dashboard/admin geçmişi.) ----
    try:
        from landing.models import AssistantConversation
        conv_cutoff = timezone.now() - timedelta(days=7)
        n, _ = AssistantConversation.objects.filter(
            user__isnull=True, updated_at__lt=conv_cutoff).delete()
        out["anon_convs_purged"] = n
    except Exception as exc:  # noqa: BLE001
        out["errors"].append(f"conv purge: {exc}")
    return out
