"""Recording that a paid account actually used the service.

Called from the entitlement endpoint, which the proxy pool hits before serving
a premium exit. That path is hot, so this must be cheap and must never raise:
a bookkeeping failure may not cost a paying customer their connection.
"""
import logging

from django.db import transaction
from django.utils import timezone

from .models import PremiumUsage

log = logging.getLogger(__name__)

# The pool asks on every premium request (it caches briefly on its side). We do
# not need that resolution -- refunds turn on days, not seconds -- so a row is
# refreshed at most once every 15 minutes. This keeps the write rate near zero
# and is a second reason the table can never become an activity log.
_MIN_WRITE_INTERVAL = 900  # seconds


def mark_premium_used(user_id) -> None:
    """Stamp that ``user_id`` consumed premium just now. Idempotent, best effort."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return
    if uid <= 0:
        return

    now = timezone.now()
    today = timezone.localdate(now)
    try:
        with transaction.atomic():
            row = PremiumUsage.objects.filter(user_id=uid).first()
            if row is None:
                PremiumUsage.objects.create(
                    user_id=uid, first_used_at=now, last_used_at=now,
                    last_used_date=today, use_days=1,
                )
                return
            new_day = row.last_used_date != today
            if not new_day and (now - row.last_used_at).total_seconds() < _MIN_WRITE_INTERVAL:
                return
            row.last_used_at = now
            if new_day:
                row.last_used_date = today
                row.use_days = (row.use_days or 0) + 1
                row.save(update_fields=["last_used_at", "last_used_date", "use_days"])
            else:
                row.save(update_fields=["last_used_at"])
    except Exception:  # noqa: BLE001 — never break the entitlement answer
        log.warning("premium usage stamp failed for user %s", user_id, exc_info=True)
