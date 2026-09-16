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
    # Yerel kayit yoksa HEMEN yeni musteri acma: webhook bir kez bozuldugunda
    # yerel satir hic olusmuyor ve ayni kisi icin HER odemede yeni bir Stripe
    # musterisi yaratiliyor. 2026-09-16'da tam bu oldu: bir kullanicinin iki
    # ayri customer'i ve iki ayri canli aboneligi olustu. Once Stripe'a sor.
    try:
        found = api.Customer.search(
            query=f"metadata['user_id']:'{user.id}' AND metadata['app']:'vpnsterr'",
            limit=20)
        # BIRDEN FAZLA eslesme olabilir: gecmiste mukerrer musteri olustuysa ya
        # da Stripe'in arama indeksi (nihai tutarli) henuz guncellenmediyse.
        # Ilkini secmek, iptal edilmis/bos bir musteriye abonelik acmak demek.
        # Once CANLI aboneligi olani, yoksa EN YENISINI tercih ediyoruz.
        live = {"active", "trialing", "past_due", "unpaid"}
        best, best_created = None, -1
        for cand in found.data:
            cid = cand.id
            try:
                subs = api.Subscription.list(customer=cid, status="all", limit=20).data
            except Exception:  # noqa: BLE001
                subs = []
            if any(sfield(sub, "status") in live for sub in subs):
                return cid
            created = sfield(cand, "created", default=0) or 0
            if created > best_created:
                best, best_created = cid, created
        if best:
            return best
    except Exception:  # noqa: BLE001 - arama yoksa/yetkisizse asagida olusturulur
        pass
    cust = api.Customer.create(
        email=user.email or None,
        metadata={"user_id": str(user.id), "app": "vpnsterr"},
    )
    return cust.id


# ============================================================
# Stripe nesne erisimi — SURUM UYUMLULUGU
#
# 2026-09-16'da bir musteri iki kez odedi ve premium HIC verilmedi. Sentry:
#   AttributeError: 'get' is a dict method, but a Session is not a dict
#   AttributeError: 'get' is a dict method, but a Invoice is not a dict
# Webhook 500 veriyordu, dolayisiyla ne abonelik aciliyor ne de bildirim
# maili gidiyordu. Uc ayri kirilma vardi, ucu de Stripe'in yeni surumlerinden:
#
#  1) stripe-python 15'te StripeObject ARTIK dict degil: .get() AttributeError
#     atiyor. __getitem__ hala calisiyor ama olmayan alanda KeyError veriyor.
#  2) Subscription.current_period_end UST SEVIYEDEN KALKTI; artik abonelik
#     KALEMINDE: subscription["items"]["data"][0]["current_period_end"].
#  3) Invoice.subscription UST SEVIYEDEN KALKTI; artik
#     invoice["parent"]["subscription_details"]["subscription"].
#
# Asagidaki yardimcilar hem eski hem yeni bicimi karsilar, boylece Stripe bir
# alani tasidiginda odeme akisi yine sessizce olmez.
# ============================================================

def sfield(obj, *path, default=None):
    """``obj`` icinde ``path`` boyunca ilerler; bulamazsa ``default``.

    Hem StripeObject hem duz dict ile calisir. Stripe nesnelerinde ``.get()``
    YOK, ``[...]`` ise olmayan alanda KeyError atiyor -- ikisini de burada
    yutuyoruz ki cagiran yerler try/except ile dolmasin.
    """
    cur = obj
    for key in path:
        if cur is None:
            return default
        try:
            cur = cur[key]
        except (KeyError, IndexError, TypeError):
            # Sayisal indeks getattr ile okunamaz; denemek TypeError atar ve
            # bu yardimcinin tek isi "asla patlamamak".
            if not isinstance(key, str):
                return default
            try:
                cur = getattr(cur, key)
            except AttributeError:
                return default
    return default if cur is None else cur


def subscription_period(stripe_sub):
    """``(start_ts, end_ts)`` -- abonelik doneminin unix zaman damgalari.

    Once ust seviyeye, sonra ilk kaleme bakar. Yeni API surumlerinde alan
    yalnizca kalemde; eski kayitlar icin ust seviye fallback duruyor.
    """
    start = sfield(stripe_sub, "current_period_start")
    end = sfield(stripe_sub, "current_period_end")
    if start is None or end is None:
        item = sfield(stripe_sub, "items", "data", 0)
        start = start if start is not None else sfield(item, "current_period_start")
        end = end if end is not None else sfield(item, "current_period_end")
    return start, end


def invoice_subscription_id(invoice):
    """Faturanin bagli oldugu abonelik id'si (eski ve yeni bicim)."""
    return (sfield(invoice, "subscription")
            or sfield(invoice, "parent", "subscription_details", "subscription"))


def amount_label(stripe_sub) -> str:
    """Bildirim maili icin "4.99 USD" gibi okunur tutar; cikaramazsa bos."""
    item = sfield(stripe_sub, "items", "data", 0)
    cents = sfield(item, "price", "unit_amount")
    ccy = (sfield(item, "price", "currency", default="") or "").upper()
    if cents is None:
        return ""
    return f"{int(cents) / 100:.2f} {ccy}".strip()
