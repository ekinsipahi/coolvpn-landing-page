"""Admin ana sayfasindaki ozet panelinin verisi.

Neden template tag? Django'nun admin index'ine ekstra context vermenin
resmi yolu AdminSite'i degistirmek; o da tum kayitli modelleri tasiyan
global bir nesneye dokunmak demek. Bir tag ile sablona veri vermek ayni
sonucu veriyor ve admin'in geri kalanina hic dokunmuyor.

Butun sayimlar TEK SORGUYA sikistirilmis toplamalarla yapilir: panel her
admin acilisinda calisiyor, 110 kullanicida farkedilmez ama 100 binde
sayfayi kilitlerdi.
"""
from datetime import timedelta

from django import template
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from landing.models import (
    AssistantConversation,
    Device,
    Order,
    PlayPurchase,
    Subscription,
    SupportTicket,
)

register = template.Library()

SOURCE_LABELS = {
    "stripe": "Kart (Stripe)",
    "crypto": "Kripto",
    "google_play": "Google Play",
    "manual": "Elle verilen",
}


@register.simple_tag
def vpn_dashboard():
    now = timezone.now()
    d1, d7, d30 = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)
    User = get_user_model()

    users = User.objects.aggregate(
        total=Count("id"),
        new_7d=Count("id", filter=Q(date_joined__gte=d7)),
        new_30d=Count("id", filter=Q(date_joined__gte=d30)),
        staff=Count("id", filter=Q(is_staff=True)),
    )

    subs = Subscription.objects.aggregate(
        active=Count("id", filter=Q(ends_at__gte=now)),
        # DISTINCT sart: bir kullanicinin ust uste binmis iki aboneligi
        # olabilir; "kac premium musteri var" sorusunun cevabi kisi sayisi.
        active_users=Count("user_id", filter=Q(ends_at__gte=now), distinct=True),
        expiring_7d=Count("id", filter=Q(ends_at__gte=now, ends_at__lte=now + timedelta(days=7))),
        new_30d=Count("id", filter=Q(created_at__gte=d30)),
    )

    by_source = [
        {"label": SOURCE_LABELS.get(r["source"], r["source"] or "—"),
         "key": r["source"], "n": r["n"]}
        for r in (Subscription.objects.filter(ends_at__gte=now)
                  .values("source").annotate(n=Count("id")).order_by("-n"))
    ]

    devices = Device.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        seen_24h=Count("id", filter=Q(last_seen__gte=d1)),
        new_7d=Count("id", filter=Q(created_at__gte=d7)),
    )
    by_platform = list(Device.objects.filter(is_active=True)
                       .values("platform").annotate(n=Count("id")).order_by("-n")[:6])

    # Gelir para birimine gore ayrilir: USD ile EUR'u toplamak anlamsiz
    # bir sayi uretirdi.
    revenue_30d = list(Order.objects.filter(status="paid", paid_at__gte=d30)
                       .values("price_currency")
                       .annotate(total=Sum("price_amount"), n=Count("id"))
                       .order_by("-total"))

    tickets = SupportTicket.objects.aggregate(
        open=Count("id", filter=Q(status=SupportTicket.STATUS_OPEN)),
        answered=Count("id", filter=Q(status=SupportTicket.STATUS_ANSWERED)),
    )
    assistant = AssistantConversation.objects.aggregate(
        escalated=Count("id", filter=Q(status=AssistantConversation.STATUS_ESCALATED)),
        open=Count("id", filter=Q(status=AssistantConversation.STATUS_OPEN)),
    )
    play = PlayPurchase.objects.aggregate(
        active=Count("id", filter=Q(state=PlayPurchase.STATE_ACTIVE)),
    )

    return {
        "users": users, "subs": subs, "by_source": by_source,
        "devices": devices, "by_platform": by_platform,
        "revenue_30d": revenue_30d, "tickets": tickets,
        "assistant": assistant, "play": play,
        "free_users": max(0, users["total"] - subs["active_users"]),
    }


@register.simple_tag
def vpn_recent():
    """Panelin altindaki "son hareketler" listeleri."""
    User = get_user_model()
    return {
        "signups": User.objects.order_by("-date_joined")[:8],
        "subs": (Subscription.objects.select_related("user")
                 .order_by("-created_at")[:8]),
        "devices": (Device.objects.select_related("user")
                    .order_by("-created_at")[:8]),
        "tickets": (SupportTicket.objects.select_related("user")
                    .exclude(status=SupportTicket.STATUS_CLOSED)
                    .order_by("-updated_at")[:8]),
    }
