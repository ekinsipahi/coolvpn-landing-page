# landing/utils.py
from typing import Dict, Optional
from django.utils.timezone import now
from .models import Subscription

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
