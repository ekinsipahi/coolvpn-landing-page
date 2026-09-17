"""Bot kalkanı açık mı? Deploy sonrası tek komutla gör.

Turnstile anahtarları yoksa doğrulama SESSİZCE kapalı olur (deploy'un
anahtarlardan önce çıkması kimseyi kilitlemesin diye). Sessiz olması iyi,
görünmez olması kötü — bu komut o farkı kapatıyor.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from landing.helpers import turnstile


class Command(BaseCommand):
    help = "Turnstile ve kayıt yüzeyinin durumunu raporlar."

    def handle(self, *args, **opts):
        ok = self.style.SUCCESS
        bad = self.style.ERROR
        warn = self.style.WARNING

        site = getattr(settings, "TURNSTILE_SITE_KEY", "")
        secret = getattr(settings, "TURNSTILE_SECRET_KEY", "")
        self.stdout.write("Turnstile")
        self.stdout.write(f"  site anahtarı   : {'var' if site else 'YOK'}")
        self.stdout.write(f"  gizli anahtar   : {'var' if secret else 'YOK'}")

        if turnstile.enabled() and site:
            self.stdout.write(ok("  durum           : AÇIK — kayıt ve checkout korunuyor"))
        elif secret and not site:
            self.stdout.write(bad("  durum           : YARIM — sunucu doğruluyor ama sayfada "
                                  "widget yok; hiç kimse geçemez!"))
        elif site and not secret:
            self.stdout.write(bad("  durum           : YARIM — sayfada widget var ama sunucu "
                                  "doğrulamıyor; koruma YOK"))
        else:
            self.stdout.write(warn("  durum           : KAPALI — bot koruması yok. "
                                   "Cloudflare > Turnstile > Add site ile iki anahtarı al, "
                                   "TURNSTILE_SITE_KEY ve TURNSTILE_SECRET_KEY olarak gir."))

        adapter = getattr(settings, "ACCOUNT_ADAPTER", "")
        closed = "ClosedSignupAdapter" in adapter
        self.stdout.write("\nKayıt yüzeyi")
        self.stdout.write(f"  /auth/email-upsert-login/  : {'Turnstile arkasında' if turnstile.enabled() else 'KORUMASIZ'}")
        self.stdout.write(("  /accounts/signup/          : kapalı" if closed
                           else bad("  /accounts/signup/          : AÇIK — captcha'sız yan kapı")))
