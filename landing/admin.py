# landing/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.conf import settings

from .models import (
    AssistantConversation,
    AssistantMessage,
    Device,
    Order,
    Subscription,
    SupportTicket,
    TicketMessage,
)


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


# =========================
# SUPPORT TICKETS — cevabı buradan yaz: inline'a yeni mesaj ekle,
# kaydedince kullanıcıya "yeni cevap" maili otomatik gider.
# =========================
class TicketMessageInline(admin.StackedInline):
    model = TicketMessage
    extra = 1
    fields = ("role", "body", "created_at")
    readonly_fields = ("created_at",)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("ref", "user_link", "subject", "category", "status_badge", "updated_at")
    list_filter = ("status", "category", "updated_at")
    search_fields = ("ref", "subject", "user__email", "user__username", "messages__body")
    readonly_fields = ("ref", "user", "created_at", "updated_at")
    inlines = [TicketMessageInline]
    date_hierarchy = "created_at"

    def user_link(self, obj):
        try:
            url = reverse(
                f"admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change",
                args=[obj.user_id],
            )
            return format_html('<a href="{}">{}</a>', url, obj.user.email or obj.user.get_username())
        except Exception:
            return obj.user_id

    user_link.short_description = "User"

    def status_badge(self, obj):
        colors = {"open": "#f59e0b", "answered": "#16a34a", "closed": "#6b7280"}
        return format_html(
            '<span style="padding:2px 8px;border-radius:8px;background:{};color:#fff;">{}</span>',
            colors.get(obj.status, "#6b7280"), obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def save_formset(self, request, form, formset, change):
        """Admin'den eklenen YENİ mesaj tanım gereği EKİP mesajıdır: rol ne
        seçilirse seçilsin staff'a çevrilir (rol 'user' kalırsa mail gitmez ve
        durum güncellenmezdi — sessiz kayıp). Sonra kullanıcıya cevap maili +
        ticket 'answered'."""
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        new_replies = []
        for m in instances:
            if m.pk is None:
                m.role = TicketMessage.ROLE_STAFF
                new_replies.append(m)
            m.save()
        formset.save_m2m()
        if new_replies:
            ticket = form.instance
            ticket.status = SupportTicket.STATUS_ANSWERED
            ticket.save(update_fields=["status", "updated_at"])
            from landing.helpers.mailer import send_ticket_replied_email
            for m in new_replies:
                send_ticket_replied_email(ticket, m.body)


# =========================
# ASSISTANT — canlı gelen kutusu. "owner_joined" işaretle + inline'a
# role=Operator mesaj ekle → widget'ta "Team" balonu olarak düşer,
# kullanıcının rozeti/zili çalar (user_unread burada artırılır).
# =========================
class AssistantMessageInline(admin.StackedInline):
    model = AssistantMessage
    extra = 1
    fields = ("role", "content", "intent", "created_at")
    readonly_fields = ("created_at",)


@admin.register(AssistantConversation)
class AssistantConversationAdmin(admin.ModelAdmin):
    list_display = ("short_id", "who", "status", "intent_flags", "owner_joined",
                    "user_unread", "updated_at")
    list_filter = ("status", "owner_joined", "updated_at")
    search_fields = ("id", "user__email", "session_key", "messages__content")
    readonly_fields = ("id", "user", "session_key", "created_at", "updated_at")
    inlines = [AssistantMessageInline]

    def short_id(self, obj):
        return str(obj.id)[:8]

    short_id.short_description = "Conv"

    def who(self, obj):
        return obj.user.email if obj.user_id else f"anon:{obj.session_key[:10]}"

    who.short_description = "Visitor"

    def save_formset(self, request, form, formset, change):
        """Admin'den eklenen YENİ mesaj operatör mesajıdır ('user' seçilmişse
        bile — yoksa rozet/zil tetiklenmezdi). Unread artar → widget'ın bir
        sonraki poll'unda rozet + sparkle zili çalar; owner_joined = AI susar."""
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        new_operator_msgs = []
        for m in instances:
            if m.pk is None and m.role != AssistantMessage.ROLE_ASSISTANT:
                m.role = AssistantMessage.ROLE_OWNER
            if m.pk is None:
                new_operator_msgs.append(m)
            m.save()
        formset.save_m2m()
        if new_operator_msgs:
            conv = form.instance
            conv.user_unread = (conv.user_unread or 0) + len(new_operator_msgs)
            if any(m.role == AssistantMessage.ROLE_OWNER for m in new_operator_msgs):
                conv.owner_joined = True
            conv.save(update_fields=["user_unread", "owner_joined", "updated_at"])
