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
