"""Read-only admin for records that exist to answer refund and chargeback
questions. Nothing here is editable: a billing record that can be edited after
the fact is worthless as evidence.
"""
from django.contrib import admin

from .models import BillingRecord, PremiumUsage, email_fingerprint


@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = ("account_deleted_at", "user_id_snapshot", "verdict",
                    "premium_use_days", "device_count", "first_paid_at")
    list_filter = ("account_deleted_at",)
    date_hierarchy = "account_deleted_at"
    search_fields = ("stripe_customer_ids", "stripe_subscription_ids", "user_id_snapshot")
    search_help_text = ("Search a Stripe id, a user id, or paste the customer's "
                        "e-mail address — the address itself is not stored, it is "
                        "matched by fingerprint.")
    readonly_fields = [f.name for f in BillingRecord._meta.fields] + ["verdict"]

    @admin.display(description="refund verdict")
    def verdict(self, obj):
        return obj.refund_verdict

    def get_search_results(self, request, queryset, search_term):
        """Let the operator paste an e-mail even though we store only its hash."""
        term = (search_term or "").strip()
        if "@" in term:
            return queryset.filter(email_sha256=email_fingerprint(term)), False
        return super().get_search_results(request, queryset, search_term)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PremiumUsage)
class PremiumUsageAdmin(admin.ModelAdmin):
    list_display = ("user_id", "use_days", "first_used_at", "last_used_at")
    readonly_fields = [f.name for f in PremiumUsage._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
