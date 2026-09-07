# landing/services/subscription.py
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from typing import Dict, Optional
from django.utils.timezone import now
from landing.models import Subscription

# senin normalize tablon (kopyalıyorum)
NORMALIZE_TABLE = {
    "m": "monthly", "month": "monthly", "monthly": "monthly",
    "s": "semi", "semi": "semi", "6": "semi", "6m": "semi",
    "6-month": "semi", "6months": "semi", "semiannual": "semi", "semi-annual": "semi",
    "a": "annual", "y": "annual", "year": "annual", "annual": "annual",
}

def normalize_plan_slug(raw: Optional[str]) -> str:
    if not raw:
        return "monthly"
    return NORMALIZE_TABLE.get(raw.strip().lower(), "monthly")

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

    # Premium aktifleşti maili — transaction commit OLDUKTAN sonra gönder ki
    # e-posta gidip de kayıt rollback olursa yalancı çıkmayalım. Gönderim zaten
    # arka plan thread'inde, isteği bekletmez.
    try:
        from django.db import transaction as _tx
        from landing.helpers.mailer import send_premium_activated_email
        _tx.on_commit(lambda: send_premium_activated_email(user, sub))
    except Exception:  # noqa: BLE001 - mail hiçbir koşulda grant'ı bozamaz
        pass
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

# kapasite mapping
_PLAN_DEVICE_CAP = {
    "monthly": 5,
    "semi": 10,
    "annual": 20,
}

def plan_device_limit(plan_key: Optional[str] = None, user=None, prefer_highest: bool = True) -> int:
    """
    Cihaz limiti döndürür.
    - Eğer plan_key verilmişse onun üzerinden hesaplar.
    - Yoksa user verilirse active subscription'ları kontrol eder.
    - prefer_highest=True olursa birden fazla aktif abonelik varsa en yüksek plan limitini kullanır.
    - fallback default: 1
    """
    # 1) doğrudan plan_key varsa
    if plan_key:
        pk = normalize_plan_slug(plan_key)
        return _PLAN_DEVICE_CAP.get(pk, 1)

    # 2) user verilmişse aktif abonelikleri kontrol et
    if user is not None:
        now_ts = now()
        active_subs = Subscription.objects.filter(user=user, ends_at__gte=now_ts).order_by("-ends_at")
        if not active_subs.exists():
            return 1
        # normalize tüm plan keyleri
        normalized = [normalize_plan_slug(getattr(s, "plan_key", None)) for s in active_subs]
        if prefer_highest:
            # tercih sırası annual > semi > monthly
            for tier in ("annual", "semi", "monthly"):
                if tier in normalized:
                    return _PLAN_DEVICE_CAP.get(tier, 1)
            return 1
        else:
            # toplama seçeneği: tüm active aboneliklerin kapasitesini topla (nadiren kullan)
            total = 0
            for pk in normalized:
                total += _PLAN_DEVICE_CAP.get(pk, 0)
            return max(1, total)

    # fallback
    return 1

