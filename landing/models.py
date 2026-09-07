# landing/models.py
import uuid as uuidlib
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("expired", "Expired"),
        ("refunded", "Refunded"),
    ]
    id = models.BigAutoField(primary_key=True)
    order_id = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    plan_key = models.CharField(max_length=20)
    price_amount = models.DecimalField(max_digits=10, decimal_places=2)
    price_currency = models.CharField(max_length=10)
    pay_currency   = models.CharField(max_length=20, blank=True, default="")
    gateway = models.CharField(max_length=40, default="nowpayments")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    np_invoice_id = models.CharField(max_length=64, blank=True, default="")
    np_payment_id = models.CharField(max_length=64, blank=True, default="")
    np_raw = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at    = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.order_id} / {self.user_id} / {self.plan_key} / {self.status}"


class Subscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan_key = models.CharField(max_length=20)
    starts_at = models.DateTimeField()
    ends_at   = models.DateTimeField()
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="subscription", null=True, blank=True)
    # Ödeme kaynağı: crypto (NOWPayments) | stripe | manual
    source = models.CharField(max_length=16, default="crypto")
    stripe_customer_id = models.CharField(max_length=64, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "ends_at"])]

    def is_active(self):
        return self.ends_at >= timezone.now()

    @property
    def active(self):
        return self.is_active()


class Device(models.Model):
    PLATFORM_CHOICES = [
        ("windows", "Windows"),
        ("macos", "macOS"),
        ("linux", "Linux"),
        ("android", "Android"),
        ("ios", "iOS"),
        ("browser", "Browser"),
        ("other", "Other"),
    ]

    id          = models.BigAutoField(primary_key=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    uuid        = models.UUIDField(default=uuidlib.uuid4, editable=False, db_index=True)
    client_uuid = models.CharField(max_length=64, blank=True, default="", db_index=True)
    platform    = models.CharField(max_length=16, choices=PLATFORM_CHOICES, default="other", db_index=True)
    name        = models.CharField(max_length=120, blank=True, default="")
    os_version  = models.CharField(max_length=64, blank=True, default="")
    app_version = models.CharField(max_length=64, blank=True, default="")
    ip          = models.GenericIPAddressField(blank=True, null=True)
    city        = models.CharField(max_length=64, blank=True, default="")
    country     = models.CharField(max_length=64, blank=True, default="")
    last_seen   = models.DateTimeField(auto_now=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    is_active   = models.BooleanField(default=True)
    last_subscription = models.ForeignKey(
        "Subscription", null=True, blank=True, on_delete=models.SET_NULL, related_name="devices_snapshot"
    )

    class Meta:
        ordering = ("-last_seen",)
        constraints = [
            models.UniqueConstraint(fields=["user", "client_uuid"], name="uniq_user_client_uuid")
        ]

    def __str__(self):
        label = self.name or self.platform
        return f"{label} ({self.user})"


class ExtensionLink(models.Model):
    """
    Eklenti cihaz bağlama akışı (nonce pairing):
      startLink() -> /extension/link?nonce=X&device_id=Y (kullanıcı onaylar)
      claim       -> nonce karşılığı imzalı hesap token'ı döner (tek kullanımlık)
    """
    nonce = models.CharField(max_length=64, unique=True, db_index=True)
    device_id = models.CharField(max_length=64, blank=True, default="")
    user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.CASCADE)
    linked_at = models.DateTimeField(null=True, blank=True)
    claimed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"link:{self.nonce[:8]}… user={self.user_id} claimed={self.claimed}"


# ============================================================
# Destek ticket'ları — dashboard'daki resmi destek kanalı.
# AI asistan (aşağıda) anlık sohbet; ticket ise takip numaralı,
# e-postayla da yürüyen kayıtlı süreç. İkisi bilerek ayrı.
# ============================================================
class SupportTicket(models.Model):
    STATUS_OPEN = "open"          # kullanıcı yazdı, cevap bekliyor
    STATUS_ANSWERED = "answered"  # ekip cevapladı, kullanıcı bekleniyor
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_ANSWERED, "Answered"),
        (STATUS_CLOSED, "Closed"),
    ]
    CATEGORY_CHOICES = [
        ("billing", "Billing & payments"),
        ("technical", "Technical problem"),
        ("account", "Account"),
        ("other", "Other"),
    ]

    id = models.BigAutoField(primary_key=True)
    # Kullanıcıya gösterilen kısa referans (VS-XXXXXX) — sıralı id sızdırmaz.
    ref = models.CharField(max_length=12, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets")
    subject = models.CharField(max_length=140)
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default="other")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [models.Index(fields=["user", "-updated_at"])]

    @staticmethod
    def new_ref() -> str:
        # 6 hex ≈ 16M olasılık; çakışırsa save uniq hatası verir, çağıran yeniler.
        return "VS-" + uuidlib.uuid4().hex[:6].upper()

    def __str__(self):
        return f"{self.ref} [{self.status}] {self.subject[:40]}"


class TicketMessage(models.Model):
    ROLE_USER = "user"
    ROLE_STAFF = "staff"
    ROLE_CHOICES = [(ROLE_USER, "User"), (ROLE_STAFF, "Staff")]

    id = models.BigAutoField(primary_key=True)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=8, choices=ROLE_CHOICES, default=ROLE_USER)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.ticket.ref} {self.role}: {self.body[:40]}"


# ============================================================
# AI asistan chatbox'ı — köşedeki anlık sohbet balonu.
# Anonim ziyaretçi session_key ile, girişli kullanıcı user ile bağlanır;
# yükseltme (bug/ödeme/insan) operatöre e-posta düşürür.
# ============================================================
class AssistantConversation(models.Model):
    STATUS_OPEN = "open"
    STATUS_ESCALATED = "escalated"  # operatöre bayraklandı
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_ESCALATED, "Escalated"),
        (STATUS_CLOSED, "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuidlib.uuid4, editable=False)
    # İkisinden biri dolu: girişli kullanıcı ya da anonim ziyaretçi oturumu.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.CASCADE, related_name="assistant_conversations")
    session_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    # Yakalanan niyet bayrakları (virgülle): bug,purchase,urgent,human,churn...
    intent_flags = models.CharField(max_length=120, blank=True, default="")
    # Operatör devraldı → AI susar, cevapları insan yazar ("Team" balonu).
    owner_joined = models.BooleanField(default=False)
    # Kullanıcının görmediği cevap sayısı → widget rozeti + zil sesi.
    user_unread = models.PositiveSmallIntegerField(default=0)
    escalated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [models.Index(fields=["user", "-updated_at"])]

    def add_flags(self, flags) -> None:
        cur = {f for f in self.intent_flags.split(",") if f}
        cur |= set(flags)
        self.intent_flags = ",".join(sorted(cur))

    def __str__(self):
        who = self.user_id or f"anon:{self.session_key[:8]}"
        return f"Conv[{who}] {self.status} {self.intent_flags}"[:60]


class AssistantMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_OWNER = "owner"  # insan operatör
    ROLE_CHOICES = [(ROLE_USER, "User"), (ROLE_ASSISTANT, "AI"), (ROLE_OWNER, "Operator")]

    id = models.UUIDField(primary_key=True, default=uuidlib.uuid4, editable=False)
    conversation = models.ForeignKey(AssistantConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    intent = models.CharField(max_length=60, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
