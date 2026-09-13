"""Kullanici odakli admin: kim, ne odemis, hangi cihazlardan baglaniyor.

landing/admin.py siparis/abonelik/cihaz tablolarini tek tek yonetiyordu ama
KULLANICI ekrani Django'nun varsayilaniydi: bir kisiye bakip "premium mi,
kac cihazi var, parasi nereden geliyor" sorusunu cevaplamak icin dort ayri
listede arama yapmak gerekiyordu. Burasi o resmi tek sayfada toplar.

Ayri dosya olmasinin sebebi pratik: admin.py'a baska bir ajan da dokunuyor,
buradaki her sey tek bir import satiriyla baglaniyor.
"""
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count, Max, Prefetch, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .models import (
    Device,
    ExtensionLink,
    Order,
    PlayPurchase,
    Subscription,
    SupportTicket,
)

User = get_user_model()

# Stripe abonelikleri KENDILIGINDEN yenilenir; kripto ve elle verilenler
# yenilenmez. Operatorun bu ikisini karistirmasi, "neden para gelmedi" ya da
# daha kotusu "neden hala para cekiliyor" demektir.
AUTO_RENEWING_SOURCES = {"stripe"}


def _admin_link(obj, label=None):
    if obj is None:
        return "—"
    try:
        url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
                      args=[obj.pk])
    except Exception:
        return str(obj)
    return format_html('<a href="{}">{}</a>', url, label or str(obj))


def _chip(text, bg, fg="#fff"):
    return format_html(
        '<span style="display:inline-block;padding:2px 8px;border-radius:9px;'
        'background:{};color:{};font-size:11px;font-weight:600;white-space:nowrap">{}</span>',
        bg, fg, text)


def _stripe_links(sub):
    """Stripe kayitlarina dogrudan git.

    Aboneligi gercekten yoneten yer Stripe; buradaki satir onun kopyasi.
    Iptal/iade icin operatorun oraya gitmesi gerekiyor, o yuzden link.
    """
    bits = []
    if sub.stripe_subscription_id:
        bits.append(('https://dashboard.stripe.com/subscriptions/%s' % sub.stripe_subscription_id,
                     sub.stripe_subscription_id))
    if sub.stripe_customer_id:
        bits.append(('https://dashboard.stripe.com/customers/%s' % sub.stripe_customer_id,
                     sub.stripe_customer_id))
    if not bits:
        return "—"
    return format_html_join(
        format_html("<br>"), '<a href="{}" target="_blank" rel="noopener">{}</a>', bits)


def renewal_label(sub):
    """"Kendiliginden yenilenir mi" — admin'de en cok yanlis anlasilan sey."""
    if sub.source in AUTO_RENEWING_SOURCES:
        return _chip("Otomatik yenilenir", "#2563eb")
    if sub.source == "google_play":
        return _chip("Play yönetiyor", "#7c3aed")
    return _chip("Yenilenmez", "#6b7280")


# ============================================================
# Kullanici sayfasindaki inline'lar — hepsi salt okunur.
# Buradan veri DEGISTIRMEK istemiyoruz: abonelik Stripe'ta, cihaz
# kaydi uctaki uygulamada yasiyor. Admin'den elle degistirmek iki
# tarafi birbirinden ayirir ve hatayi gizler.
# ============================================================
class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class UserSubscriptionInline(ReadOnlyInline):
    model = Subscription
    fk_name = "user"
    verbose_name_plural = "Abonelikler"
    fields = ("plan_key", "source", "renewal", "starts_at", "ends_at", "durum", "stripe")
    readonly_fields = fields
    ordering = ("-ends_at",)

    def durum(self, obj):
        active = bool(obj.ends_at and obj.ends_at >= timezone.now())
        if not active:
            return _chip("Bitti", "#ef4444")
        days = (obj.ends_at - timezone.now()).days
        return _chip(f"Aktif · {days} gün", "#16a34a" if days > 7 else "#f59e0b")

    def renewal(self, obj):
        return renewal_label(obj)
    renewal.short_description = "Yenileme"

    def stripe(self, obj):
        return _stripe_links(obj)


class UserDeviceInline(ReadOnlyInline):
    model = Device
    fk_name = "user"
    verbose_name_plural = "Cihazlar"
    fields = ("platform", "name", "client_uuid", "nerede", "app_version", "last_seen", "durum")
    readonly_fields = fields
    ordering = ("-last_seen",)

    def nerede(self, obj):
        parts = [p for p in (obj.city, obj.country) if p]
        return ", ".join(parts) or "—"
    nerede.short_description = "Konum"

    def durum(self, obj):
        if not obj.is_active:
            return _chip("Pasif", "#6b7280")
        if obj.last_seen and obj.last_seen >= timezone.now() - timedelta(days=1):
            return _chip("Son 24 saat", "#16a34a")
        return _chip("Aktif", "#0ea5e9")
    durum.short_description = "Durum"


class UserOrderInline(ReadOnlyInline):
    model = Order
    fk_name = "user"
    verbose_name_plural = "Siparişler"
    fields = ("order_id", "plan_key", "tutar", "gateway", "status", "created_at", "paid_at")
    readonly_fields = fields
    ordering = ("-created_at",)

    def tutar(self, obj):
        return f"{obj.price_amount} {obj.price_currency}"


class UserTicketInline(ReadOnlyInline):
    model = SupportTicket
    fk_name = "user"
    verbose_name_plural = "Destek talepleri"
    fields = ("ref", "subject", "category", "status", "updated_at")
    readonly_fields = fields
    ordering = ("-updated_at",)


class UserPlayPurchaseInline(ReadOnlyInline):
    model = PlayPurchase
    fk_name = "user"
    verbose_name_plural = "Google Play satın alımları"
    fields = ("product_id", "plan_key", "state", "expires_at", "device_uuid", "updated_at")
    readonly_fields = fields


# ============================================================
# Filtreler
# ============================================================
class PremiumFilter(admin.SimpleListFilter):
    title = "plan"
    parameter_name = "vpn_plan"

    def lookups(self, request, model_admin):
        return (("premium", "Premium (aktif)"), ("expired", "Süresi dolmuş"),
                ("free", "Hiç ödeme yapmamış"))

    def queryset(self, request, qs):
        now = timezone.now()
        if self.value() == "premium":
            return qs.filter(subscriptions__ends_at__gte=now).distinct()
        if self.value() == "expired":
            # Aboneligi VAR ama hicbiri aktif degil.
            return qs.filter(subscriptions__isnull=False).exclude(
                subscriptions__ends_at__gte=now).distinct()
        if self.value() == "free":
            return qs.filter(subscriptions__isnull=True)
        return qs


class SubscriptionSourceFilter(admin.SimpleListFilter):
    title = "ödeme kaynağı (aktif abonelik)"
    parameter_name = "vpn_source"

    def lookups(self, request, model_admin):
        return (("stripe", "Kart (Stripe)"), ("crypto", "Kripto"),
                ("google_play", "Google Play"), ("manual", "Elle verilen"))

    def queryset(self, request, qs):
        if not self.value():
            return qs
        return qs.filter(subscriptions__source=self.value(),
                         subscriptions__ends_at__gte=timezone.now()).distinct()


class HasDevicesFilter(admin.SimpleListFilter):
    title = "cihaz"
    parameter_name = "vpn_devices"

    def lookups(self, request, model_admin):
        return (("yes", "Cihaz bağlamış"), ("no", "Hiç cihaz yok"),
                ("recent", "Son 24 saatte bağlanmış"))

    def queryset(self, request, qs):
        if self.value() == "yes":
            return qs.filter(devices__isnull=False).distinct()
        if self.value() == "no":
            return qs.filter(devices__isnull=True)
        if self.value() == "recent":
            return qs.filter(devices__last_seen__gte=timezone.now() - timedelta(days=1)).distinct()
        return qs


# ============================================================
# KULLANICI ADMIN
# ============================================================
class VpnsterrUserAdmin(DjangoUserAdmin):
    # Sutun sayisi bilerek dar tutuldu: filtre paneli + sol menuyle birlikte
    # dokuzuncu sutun tablodan tasip kirpiliyordu. Yetki rozeti "kim"in icine
    # tasindi.
    list_display = ("id", "kim", "plan_rozeti", "yenileme", "cihaz_sayisi",
                    "son_gorulme", "destek", "kayit")
    list_display_links = ("id", "kim")
    list_filter = (PremiumFilter, SubscriptionSourceFilter, HasDevicesFilter,
                   "is_staff", "is_superuser", "is_active", "date_joined")
    search_fields = ("email", "username", "first_name", "last_name",
                     "devices__client_uuid", "devices__uuid", "devices__name",
                     "subscriptions__stripe_customer_id",
                     "subscriptions__stripe_subscription_id",
                     "orders__order_id")
    ordering = ("-date_joined",)
    list_per_page = 50
    date_hierarchy = "date_joined"

    inlines = [UserSubscriptionInline, UserDeviceInline, UserOrderInline,
               UserPlayPurchaseInline, UserTicketInline]

    actions = ["ver_1_ay", "ver_1_yil", "premiumu_bitir", "cihazlari_kapat"]

    def get_fieldsets(self, request, obj=None):
        base = super().get_fieldsets(request, obj)
        if obj is None:
            return base
        return ((("Özet"), {"fields": ("ozet",)}),) + tuple(base)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            ro.append("ozet")
        return ro

    def get_queryset(self, request):
        """Listedeki her satir icin abonelik/cihaz sayilmasi gerekiyor.

        Bunu Python'da yapmak 50 satirlik bir sayfada yuzlerce sorgu demekti;
        tek sorguda annotate ediliyor.
        """
        now = timezone.now()
        return (super().get_queryset(request)
                # Aktif abonelikleri TEK ek sorguda getir. Bunsuz "Yenileme"
                # kolonu her satir icin ayri sorgu atiyordu -- 50 satirlik
                # sayfada 50 fazladan sorgu.
                .prefetch_related(Prefetch(
                    "subscriptions",
                    queryset=Subscription.objects.filter(ends_at__gte=now).order_by("-ends_at"),
                    to_attr="_active_list"))
                .annotate(
                    _devices=Count("devices", distinct=True),
                    _devices_active=Count("devices", filter=Q(devices__is_active=True), distinct=True),
                    _last_seen=Max("devices__last_seen"),
                    _active_subs=Count("subscriptions",
                                       filter=Q(subscriptions__ends_at__gte=now), distinct=True),
                    _sub_ends=Max("subscriptions__ends_at"),
                    _open_tickets=Count("tickets",
                                        filter=~Q(tickets__status=SupportTicket.STATUS_CLOSED),
                                        distinct=True),
                ))

    # ---- liste kolonlari ----
    def kim(self, obj):
        name = obj.get_full_name()
        rozet = ""
        if obj.is_superuser:
            rozet = _chip("superuser", "#111827")
        elif obj.is_staff:
            rozet = _chip("staff", "#374151")
        return format_html("<strong>{}</strong> {}{}", obj.email or obj.get_username(), rozet,
                           format_html("<br><span class='mini quiet'>{}</span>", name) if name else "")
    kim.short_description = "Kullanıcı"
    kim.admin_order_field = "email"

    def plan_rozeti(self, obj):
        if obj._active_subs:
            days = (obj._sub_ends - timezone.now()).days if obj._sub_ends else 0
            return format_html("{} <span class='mini quiet'>{}</span>",
                               _chip("PREMIUM", "#16a34a"),
                               f"{days} gün ({obj._sub_ends:%d.%m.%Y})" if obj._sub_ends else "")
        if obj._sub_ends:
            return format_html("{} <span class='mini quiet'>{}</span>",
                               _chip("Bitti", "#ef4444"), f"{obj._sub_ends:%d.%m.%Y}")
        return _chip("Free", "#9ca3af")
    plan_rozeti.short_description = "Plan"
    plan_rozeti.admin_order_field = "_sub_ends"

    def yenileme(self, obj):
        active = getattr(obj, "_active_list", None)
        if active is None:  # prefetch'siz bir yoldan gelinirse (ornegin export)
            active = list(obj.subscriptions.filter(ends_at__gte=timezone.now())
                          .order_by("-ends_at"))
        return renewal_label(active[0]) if active else "—"
    yenileme.short_description = "Yenileme"

    def cihaz_sayisi(self, obj):
        if not obj._devices:
            return "—"
        url = reverse("admin:landing_device_changelist") + f"?user__id__exact={obj.pk}"
        return format_html('<a href="{}">{} aktif / {} toplam</a>',
                           url, obj._devices_active, obj._devices)
    cihaz_sayisi.short_description = "Cihazlar"
    cihaz_sayisi.admin_order_field = "_devices"

    def son_gorulme(self, obj):
        # Django'nun uzun tarih bicimi ("Sept. 13, 2026, 4:43 p.m.") sutunu
        # gereksiz genisletiyordu; tabloyu yatay kaydirmaya iten seylerden biriydi.
        return f"{obj._last_seen:%d.%m.%Y %H:%M}" if obj._last_seen else "—"
    son_gorulme.short_description = "Son görülme"
    son_gorulme.admin_order_field = "_last_seen"

    def kayit(self, obj):
        return f"{obj.date_joined:%d.%m.%Y}"
    kayit.short_description = "Kayıt"
    kayit.admin_order_field = "date_joined"

    def destek(self, obj):
        if not obj._open_tickets:
            return "—"
        url = reverse("admin:landing_supportticket_changelist") + f"?user__id__exact={obj.pk}"
        return format_html('<a href="{}">{}</a>', url, _chip(f"{obj._open_tickets} açık", "#f59e0b"))
    destek.short_description = "Destek"
    destek.admin_order_field = "_open_tickets"

    # ---- kullanici sayfasindaki ozet paneli ----
    def ozet(self, obj):
        from landing.helpers.subscription import plan_device_limit

        now = timezone.now()
        subs = list(obj.subscriptions.order_by("-ends_at"))
        active = [s for s in subs if s.ends_at and s.ends_at >= now]
        devices = list(obj.devices.all())
        online = [d for d in devices if d.last_seen and d.last_seen >= now - timedelta(days=1)]
        paid = [o for o in obj.orders.all() if o.status == "paid"]
        limit = plan_device_limit(user=obj)

        rows = [
            ("Plan", (format_html("{} · bitiş {} · {}", _chip("PREMIUM", "#16a34a"),
                                  f"{active[0].ends_at:%d.%m.%Y %H:%M}", renewal_label(active[0]))
                      if active else _chip("Free", "#9ca3af"))),
            ("Ödeme kaynağı", ", ".join(sorted({s.source for s in active})) or "—"),
            ("Stripe", _stripe_links(active[0]) if active else "—"),
            ("Cihaz", format_html("{} kullanılıyor / {} hak · {} son 24 saatte",
                                  len([d for d in devices if d.is_active]), limit, len(online))),
            ("Toplam ödeme", ", ".join(
                f"{sum(o.price_amount for o in paid if o.price_currency == c)} {c}"
                for c in sorted({o.price_currency for o in paid})) or "—"),
            ("Abonelik geçmişi", f"{len(subs)} kayıt, {len(active)} aktif"),
            ("Kayıt", f"{obj.date_joined:%d.%m.%Y %H:%M}"),
            ("Son giriş", f"{obj.last_login:%d.%m.%Y %H:%M}" if obj.last_login else "hiç"),
        ]
        if active and active[0].source in AUTO_RENEWING_SOURCES:
            rows.append(("Uyarı", format_html(
                '<span style="color:#b45309">Bu abonelik Stripe tarafından yönetiliyor. '
                'Buradan tarih değiştirmek Stripe’ı etkilemez — iptal/iade Stripe panelinden '
                'yapılmalı, yoksa iki taraf birbirini tutmaz.</span>')))

        return format_html(
            '<table style="border-collapse:collapse">{}</table>',
            format_html_join("", '<tr><th style="text-align:left;padding:3px 14px 3px 0;'
                                 'vertical-align:top;font-weight:600">{}</th>'
                                 '<td style="padding:3px 0">{}</td></tr>', rows))
    ozet.short_description = "Özet"

    # ---- aksiyonlar ----
    def _grant(self, request, queryset, days, label):
        now = timezone.now()
        n = 0
        for user in queryset:
            latest = user.subscriptions.order_by("-ends_at").first()
            start = latest.ends_at if (latest and latest.ends_at and latest.ends_at > now) else now
            Subscription.objects.create(
                user=user, plan_key="annual" if days >= 365 else "monthly",
                starts_at=start, ends_at=start + timedelta(days=days), source="manual")
            n += 1
        # Bilerek e-posta gonderilmiyor: "yeni abonelik" bildirimi gercek
        # satislari takip etmek icin, elle verilen plan onu kirletmesin.
        self.message_user(request, f"{n} kullanıcıya {label} premium verildi "
                                   f"(kaynak: elle, e-posta gönderilmedi).", messages.SUCCESS)

    @admin.action(description="Premium ver — 1 ay (elle)")
    def ver_1_ay(self, request, queryset):
        self._grant(request, queryset, 30, "1 aylık")

    @admin.action(description="Premium ver — 1 yıl (elle)")
    def ver_1_yil(self, request, queryset):
        self._grant(request, queryset, 365, "1 yıllık")

    @admin.action(description="Premium'u bitir (şimdi sonlandır)")
    def premiumu_bitir(self, request, queryset):
        now = timezone.now()
        qs = Subscription.objects.filter(user__in=queryset, ends_at__gte=now)
        stripe_left = qs.filter(source__in=AUTO_RENEWING_SOURCES).count()
        n = qs.update(ends_at=now)
        self.message_user(request, f"{n} abonelik sonlandırıldı.", messages.SUCCESS)
        if stripe_left:
            self.message_user(
                request,
                f"DİKKAT: bunların {stripe_left} tanesi Stripe aboneliği. Burada süre bitti "
                f"ama Stripe kartı çekmeye DEVAM EDER — Stripe panelinden de iptal et.",
                messages.WARNING)

    @admin.action(description="Tüm cihazlarını pasifleştir")
    def cihazlari_kapat(self, request, queryset):
        n = Device.objects.filter(user__in=queryset, is_active=True).update(is_active=False)
        self.message_user(request, f"{n} cihaz pasifleştirildi.", messages.SUCCESS)


# Baska bir uygulama User'i zaten cikarmis olabilir; kayit yoksa
# unregister NotRegistered atar ve TUM admin acilmaz olurdu.
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, VpnsterrUserAdmin)


# ============================================================
# Kayitli olmayan modeller
# ============================================================
@admin.register(ExtensionLink)
class ExtensionLinkAdmin(admin.ModelAdmin):
    list_display = ("nonce_kisa", "user", "device_id", "claimed", "linked_at", "created_at")
    list_filter = ("claimed", "created_at")
    search_fields = ("nonce", "device_id", "user__email", "user__username")
    readonly_fields = ("nonce", "device_id", "user", "linked_at", "claimed", "created_at")
    date_hierarchy = "created_at"
    list_select_related = ("user",)

    def nonce_kisa(self, obj):
        return f"{obj.nonce[:10]}…"
    nonce_kisa.short_description = "Nonce"


@admin.register(PlayPurchase)
class PlayPurchaseAdmin(admin.ModelAdmin):
    list_display = ("product_id", "user", "plan_key", "state_rozeti", "expires_at",
                    "subscription", "updated_at")
    list_filter = ("state", "plan_key", "product_id", "updated_at")
    search_fields = ("purchase_token", "user__email", "user__username", "device_uuid")
    readonly_fields = ("purchase_token", "user", "product_id", "plan_key", "state",
                       "expires_at", "subscription", "device_uuid", "raw",
                       "created_at", "updated_at")
    date_hierarchy = "updated_at"
    list_select_related = ("user", "subscription")

    def state_rozeti(self, obj):
        colors = {PlayPurchase.STATE_ACTIVE: "#16a34a",
                  PlayPurchase.STATE_EXPIRED: "#ef4444"}
        return _chip(obj.state, colors.get(obj.state, "#6b7280"))
    state_rozeti.short_description = "Durum"
