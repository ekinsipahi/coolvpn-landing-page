"""Billing records that outlive the account they belong to.

WHY THIS APP EXISTS
-------------------
``account_delete`` calls ``user.delete()``, so every Subscription, Order and
Device cascades away with the account. That is correct for privacy and it is
what the delete page promises -- but it also destroys the only evidence we have
for two questions we are still legally on the hook for after the account is
gone:

  1. "I paid and never used it, refund me."  Our refund policy grants a full
     refund only for an UNUSED subscription. With the account deleted we could
     neither grant nor refuse that honestly.
  2. A chargeback arriving weeks later. The card networks give the cardholder
     months; Stripe gives us days to answer with evidence. "We deleted it" is
     not evidence.

On 2026-09-16 exactly this happened: a customer was charged twice, cancelled,
deleted his account, and nothing at all was left on our side -- the whole story
had to be reconstructed from Stripe's API.

WHAT THIS IS NOT
----------------
It is NOT an activity log. The privacy policy says "Account and billing records
are kept for statutory periods ... Activity logs are never retained because they
are never created", and that stays true: we keep no connection history, no
timestamps per session, no IP, no destination. What we keep is one aggregate
billing fact per account -- first use, last use, how many distinct days -- which
is the minimum needed to administer our own refund rule and defend a chargeback
(GDPR Art. 6(1)(f) and Art. 17(3)(e); Estonian Accounting Act retention).

The e-mail address is NOT kept. Only a salted SHA-256 of it, so a returning
customer can still be matched but our database holds no addresses of people who
asked to be deleted. The identity behind a record is resolvable only through
Stripe, which keeps the payment record regardless of what we do.
"""
import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone


def email_fingerprint(email: str) -> str:
    """Salted SHA-256 of a normalised e-mail address.

    Deliberately NOT derived from SECRET_KEY: the key gets rotated, and a
    rotation must not silently orphan every record we kept in order to answer
    refund requests. Changing RETENTION_EMAIL_SALT breaks matching for records
    written before the change -- treat it as permanent.
    """
    norm = (email or "").strip().lower()
    if not norm:
        return ""
    salt = getattr(settings, "RETENTION_EMAIL_SALT", "") or "vpnsterr-retention-v1"
    return hashlib.sha256(f"{salt}:{norm}".encode("utf-8")).hexdigest()


class PremiumUsage(models.Model):
    """Did this account ever actually consume the premium service?

    Written when the proxy pool asks ``extension_entitlement`` whether a device
    is premium and we answer yes -- i.e. the moment a paid exit is about to be
    served. That is the closest thing to "a VPN connection was established with
    your Premium account", which is the exact wording our refund policy turns on.

    One row per account, overwritten in place. There is no history here by
    design: a row that accumulated one timestamp per connection would be an
    activity log, which we promise not to create.

    ``user_id`` is a plain integer, not a ForeignKey, so that deleting the
    account does not cascade this away before :func:`retention.signals` can fold
    it into a :class:`BillingRecord`. The signal deletes it explicitly.
    """

    user_id = models.PositiveIntegerField(unique=True, db_index=True)
    first_used_at = models.DateTimeField()
    last_used_at = models.DateTimeField()
    last_used_date = models.DateField()
    use_days = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "premium usage"
        verbose_name_plural = "premium usage"

    def __str__(self):
        return f"user {self.user_id}: {self.use_days} day(s), last {self.last_used_at:%Y-%m-%d}"


class BillingRecord(models.Model):
    """What survives an account deletion. No ForeignKey anywhere, on purpose."""

    # --- who, pseudonymously ------------------------------------------------
    user_id_snapshot = models.PositiveIntegerField(db_index=True)
    email_sha256 = models.CharField(max_length=64, blank=True, default="", db_index=True)
    account_created_at = models.DateTimeField(null=True, blank=True)
    account_deleted_at = models.DateTimeField(default=timezone.now, db_index=True)

    # --- what they bought ---------------------------------------------------
    # Stripe ids are the bridge back to the payment record, and the only way to
    # recover the identity behind this row when a chargeback actually arrives.
    stripe_customer_ids = models.TextField(blank=True, default="")
    stripe_subscription_ids = models.TextField(blank=True, default="")
    subscriptions = models.JSONField(default=list, blank=True)
    orders = models.JSONField(default=list, blank=True)
    first_paid_at = models.DateTimeField(null=True, blank=True)
    last_period_end = models.DateTimeField(null=True, blank=True)

    # --- did they use it (the refund question) ------------------------------
    premium_first_used_at = models.DateTimeField(null=True, blank=True)
    premium_last_used_at = models.DateTimeField(null=True, blank=True)
    premium_use_days = models.PositiveIntegerField(default=0)
    device_count = models.PositiveIntegerField(default=0)
    device_last_seen_at = models.DateTimeField(null=True, blank=True)

    note = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ("-account_deleted_at",)
        indexes = [models.Index(fields=["email_sha256", "-account_deleted_at"])]

    def __str__(self):
        return f"billing record user={self.user_id_snapshot} deleted={self.account_deleted_at:%Y-%m-%d}"

    # -- helpers the admin and the refund_check command both use -------------

    @property
    def paid(self) -> bool:
        return self.first_paid_at is not None

    @property
    def used_after_purchase(self) -> bool:
        """True when premium was consumed at or after the first payment.

        This is the literal test in the refund policy: "no VPN connection was
        established with your Premium account after the purchase".
        """
        if not self.premium_first_used_at:
            return False
        if not self.first_paid_at:
            return True
        return self.premium_last_used_at is not None and self.premium_last_used_at >= self.first_paid_at

    @property
    def refund_verdict(self) -> str:
        if not self.paid:
            return "never paid — nothing to refund"
        if self.used_after_purchase:
            return f"USED ({self.premium_use_days} day(s)) — not eligible under the unused-service rule"
        return "UNUSED after purchase — eligible for a full refund"
