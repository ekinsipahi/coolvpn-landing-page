# landing/helpers/stripe_gw.py
# Stripe abonelik entegrasyonu — self-bootstrapping:
# Product/Price yoksa lookup_key ile İLK kullanımda oluşturur (idempotent).

import stripe
from django.conf import settings

# lookup_key -> (isim, cent, interval, interval_count)
PLAN_PRICES = {
    "monthly": ("vpnsterr_monthly", "VPNsterr Premium — Monthly", 499, "month", 1),
    "semi":    ("vpnsterr_semi",    "VPNsterr Premium — 6 Months", 2499, "month", 6),
    "annual":  ("vpnsterr_annual",  "VPNsterr Premium — Annual",  3999, "year", 1),
}

_price_cache = {}


def stripe_enabled() -> bool:
    return bool(getattr(settings, "STRIPE_SECRET_KEY", ""))


def _api():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def ensure_price(plan_key: str) -> str:
    """Plana ait Stripe Price id'sini döner; yoksa Product+Price oluşturur."""
    if plan_key not in PLAN_PRICES:
        plan_key = "monthly"
    if plan_key in _price_cache:
        return _price_cache[plan_key]

    lookup, name, cents, interval, count = PLAN_PRICES[plan_key]
    api = _api()

    found = api.Price.list(lookup_keys=[lookup], active=True, limit=1)
    if found.data:
        _price_cache[plan_key] = found.data[0].id
        return found.data[0].id

    product = api.Product.create(
        name=name,
        metadata={"plan_key": plan_key, "app": "vpnsterr"},
    )
    price = api.Price.create(
        product=product.id,
        unit_amount=cents,
        currency="usd",
        recurring={"interval": interval, "interval_count": count},
        lookup_key=lookup,
        metadata={"plan_key": plan_key},
    )
    _price_cache[plan_key] = price.id
    return price.id


def get_or_create_customer(user) -> str:
    """Kullanıcının Stripe customer id'si; önce eski aboneliklerde arar."""
    from landing.models import Subscription

    prev = (
        Subscription.objects
        .filter(user=user)
        .exclude(stripe_customer_id="")
        .order_by("-created_at")
        .values_list("stripe_customer_id", flat=True)
        .first()
    )
    if prev:
        return prev
    api = _api()
    cust = api.Customer.create(
        email=user.email or None,
        metadata={"user_id": str(user.id), "app": "vpnsterr"},
    )
    return cust.id
