# landing/services/subscription.py
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

PLAN_DURATIONS = {
    "monthly": timedelta(days=30),
    "semi":    timedelta(days=182),   # ~6 ay
    "annual":  timedelta(days=365),
}

@transaction.atomic
def grant_subscription(user, plan_key: str, order=None):
    """
    Her PAID order sonrası çağır.
    - Mevcut aktif abonelik varsa, bitişten devam ederek uzatır.
    - Yoksa 'şimdi'den başlatır.
    - Her çağrıda YENİ bir Subscription kaydı oluşturur ve (varsa) order'a bağlar.
    Idempotency:
      - Eğer order already has subscription → direkt onu döndürür (çift IPN vs. durumlarında güvenli).
    """
    # Order zaten bir aboneliğe bağlanmışsa tekrar yaratma
    if order and getattr(order, "subscription", None):
        return order.subscription

    from landing.models import Subscription  # circular import'tan kaçınmak için lokal import

    now = timezone.now()
    duration = PLAN_DURATIONS.get(plan_key, PLAN_DURATIONS["monthly"])

    # Kullanıcının en güncel aboneliğini kilitleyip al
    latest = (
        Subscription.objects
        .select_for_update()
        .filter(user=user)
        .order_by("-ends_at")
        .first()
    )

    base_start = latest.ends_at if (latest and latest.ends_at and latest.ends_at > now) else now
    starts_at  = base_start
    ends_at    = base_start + duration

    sub = Subscription.objects.create(
        user=user,
        plan_key=plan_key,
        starts_at=starts_at,
        ends_at=ends_at,
        order=order  # None olabilir
    )
    return sub


# landing/helpers/subscription.py

from typing import Optional

# Plan → cihaz limiti (iş gereksinimi)
_DEVICE_LIMITS = {
    "monthly": 5,
    "semi": 10,          # normalize edilmiş 'semi' anahtarı
    "semi-annual": 10,   # olası eski/ham değer için güvenli eşleştirme
    "annual": 20,
}

def plan_device_limit(plan_key: Optional[str]) -> int:
    """
    Aktif plana göre cihaz limitini döndürür.
    - monthly  → 5
    - semi     → 10
    - annual   → 20
    - plan yok/Free → 1

    Not: plan_key bazen ham gelebilir; normalize etmeye çalışıyoruz.
    """
    if not plan_key:
        return 1  # Free hesap
    try:
        # normalize etmeyi dene; yoksa ham değeri kullan
        from landing.helpers.plans import normalize_plan_slug
        key = normalize_plan_slug(plan_key)
    except Exception:
        key = (plan_key or "").strip().lower()

    # ‘semi-annual’ gibi varyantları da kapsa
    if key not in _DEVICE_LIMITS and key == "semi-annual":
        key = "semi"

    return _DEVICE_LIMITS.get(key, 1)  # bilinmeyen planlarda korumacı davran
