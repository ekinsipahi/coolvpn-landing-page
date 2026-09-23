from django.apps import AppConfig


class LandingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'landing'

    def ready(self):
        # Wire the pre_delete → archive receiver (chat-log preservation).
        from . import signals  # noqa: F401
