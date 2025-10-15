# landing/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.conf import settings

from .models import Order, Subscription, Device


# =========================
# INLINE: Order → Subscription (OneToOne)
# =========================
class SubscriptionInline(admin.StackedInline):
    model = Subscription
    can_delete = False
    fk_name = "order"  # Subscription.order — OneToOne(Order)
    extra = 0
    readonly_fields = ("user", "plan_key", "starts_at", "ends_at", "created_at")

    def has_add_permission(self, request, obj=None):
        # Order başına maksimum 1 subscription; admin’den eklemeyi kapat
        return False

    def has_change_permission(self, request, obj=None):
        # Inline’ı sadece görüntüle
        return False


# =========================
# ORDER ADMIN
# =========================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "user_link",
        "plan_key",
        "amount_ccy",
        "gateway",
        "status",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "gateway", "price_currency", "plan_key", "created_at")
    search_fields = ("order_id", "user__email", "user__username", "np_invoice_id", "np_payment_id")
    date_hierarchy = "created_at"
    list_per_page = 50

    readonly_fields = (
        "order_id",
        "user",
        "plan_key",
        "price_amount",
        "price_currency",
        "pay_currency",
        "gateway",
        "status",
        "np_invoice_id",
        "np_payment_id",
        "np_raw",
        "created_at",
        "paid_at",
    )

    inlines = [SubscriptionInline]

    # ---- Geliştirme/test için pratik actionlar
    actions = ["mark_paid_and_grant", "mark_failed"]

    def user_link(self, obj):
        # admin’de kullanıcıyı linkli göster (reverse ile güvenli)
        try:
            url = reverse(
                f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change",
                args=[obj.user_id],
            )
            label = obj.user.get_username() or obj.user_id
            return format_html('<a href="{}">{}</a>', url, label)
        except Exception:
            # fallback
            return obj.user.get_username() or obj.user_id

    user_link.short_description = "User"

    def amount_ccy(self, obj):
        return f"{obj.price_amount:.2f} {obj.price_currency}"

    amount_ccy.short_description = "Amount"

    def mark_paid_and_grant(self, request, queryset):
        """
        DEV/test amaçlı: seçili siparişleri 'paid' yapar, paid_at atar ve Subscription verir.
        Production’da KULLANMA; DEBUG koşulu ile sınırlı.
        """
        if not getattr(settings, "DEBUG", False):
            self.message_user(
                request,
                "Bu işlem sadece DEBUG=True iken kullanılabilir.",
                level="error",
            )
            return

        from landing.helpers.subscription import grant_subscription

        count = 0
        now = timezone.now()
        for order in queryset.select_related("user"):
            if order.status == "paid":
                continue
            order.status = "paid"
            order.paid_at = now
            order.save(update_fields=["status", "paid_at"])
            grant_subscription(order.user, order.plan_key, order=order)
            count += 1
        self.message_user(request, f"{count} sipariş paid yapıldı ve abonelik verildi.")

    mark_paid_and_grant.short_description = "Mark as PAID + grant subscription (DEV)"

    def mark_failed(self, request, queryset):
        updated = queryset.exclude(status="paid").update(status="failed")
        self.message_user(request, f"{updated} sipariş failed olarak işaretlendi.")

    mark_failed.short_description = "Mark as FAILED (not for paid orders)"


# =========================
# INLINE: Subscription → snapshot olarak bağlı cihazlar
#   (Device.last_subscription, related_name='devices_snapshot')
# =========================
class DevicesSnapshotInline(admin.TabularInline):
    model = Device
    fields = ("uuid", "client_uuid", "user_link", "platform", "name", "is_active", "last_seen", "created_at")
    readonly_fields = ("uuid", "client_uuid", "user_link", "platform", "name", "is_active", "last_seen", "created_at")
    extra = 0
    can_delete = False
    verbose_name = "Device (snapshot)"
    verbose_name_plural = "Devices (snapshot)"

    def user_link(self, obj):
        try:
            url = reverse(
                f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change",
                args=[obj.user_id],
            )
            label = obj.user.get_username() or obj.user_id
            return format_html('<a href="{}">{}</a>', url, label)
        except Exception:
            return obj.user_id

    user_link.short_description = "User"


# =========================
# SUBSCRIPTION ADMIN
# =========================
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user_link", "plan_key", "starts_at", "ends_at", "is_active_badge", "order_link")
    list_filter = ("plan_key", "starts_at", "ends_at")
    search_fields = ("user__email", "user__username", "order__order_id")
    date_hierarchy = "starts_at"
    readonly_fields = ("created_at",)

    inlines = [DevicesSnapshotInline]

    def user_link(self, obj):
        try:
            url = reverse(
                f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change",
                args=[obj.user_id],
            )
            label = obj.user.get_username() or obj.user_id
            return format_html('<a href="{}">{}</a>', url, label)
        except Exception:
            return obj.user

    user_link.short_description = "User"

    def order_link(self, obj):
        if not obj.order_id:
            return "-"
        try:
            url = reverse("admin:landing_order_change", args=[obj.order_id])
            return format_html('<a href="{}">{}</a>', url, obj.order.order_id)
        except Exception:
            return obj.order_id

    order_link.short_description = "Order"

    def is_active_badge(self, obj):
        active = bool(obj.ends_at and obj.ends_at >= timezone.now())
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;background:{};color:#fff;">{}</span>',
            "#16a34a" if active else "#ef4444",
            "Active" if active else "Expired",
        )

    is_active_badge.short_description = "Status"


# =========================
# DEVICE ADMIN
# =========================
@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "client_uuid",
        "user_link",
        "platform",
        "name",
        "is_active_badge",
        "last_seen",
        "created_at",
        "last_subscription_link",
    )
    list_filter = (
        "platform",
        "is_active",
        ("last_seen", admin.DateFieldListFilter),
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "uuid",
        "client_uuid",
        "name",
        "user__username",
        "user__email",
        "country",
        "city",
    )
    readonly_fields = (
        "uuid",
        "client_uuid",
        "user",
        "platform",
        "name",
        "os_version",
        "app_version",
        "ip",
        "city",
        "country",
        "last_seen",
        "created_at",
        "is_active",
        "last_subscription",
    )
    date_hierarchy = "created_at"
    list_per_page = 50

    actions = ["activate_devices", "deactivate_devices"]

    def user_link(self, obj):
        try:
            url = reverse(
                f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change",
                args=[obj.user_id],
            )
            label = obj.user.get_username() or obj.user_id
            return format_html('<a href="{}">{}</a>', url, label)
        except Exception:
            return obj.user_id

    user_link.short_description = "User"

    def last_subscription_link(self, obj):
        if not obj.last_subscription_id:
            return "-"
        try:
            url = reverse("admin:landing_subscription_change", args=[obj.last_subscription_id])
            return format_html('<a href="{}">#{}</a>', url, obj.last_subscription_id)
        except Exception:
            return obj.last_subscription_id

    last_subscription_link.short_description = "Last Sub."

    def is_active_badge(self, obj):
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;background:{};color:#fff;">{}</span>',
            "#16a34a" if obj.is_active else "#6b7280",
            "Active" if obj.is_active else "Inactive",
        )

    is_active_badge.short_description = "Device"

    # Basit toplu aksiyonlar (opsiyonel)
    def activate_devices(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} cihaz aktif edildi.")

    activate_devices.short_description = "Activate selected devices"

    def deactivate_devices(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} cihaz pasif edildi.")

    deactivate_devices.short_description = "Deactivate selected devices"
