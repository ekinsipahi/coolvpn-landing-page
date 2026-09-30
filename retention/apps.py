from django.apps import AppConfig


class RetentionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "retention"
    verbose_name = "Billing retention"

    def ready(self):
        from . import signals  # noqa: F401  — connects the pre_delete receiver
