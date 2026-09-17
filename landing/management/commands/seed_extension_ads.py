"""Ucretsiz plandaki tanitim bannerlarini kurar.

NEDEN KOMUT, ELLE ADMIN DEGIL:
Reklam gorunmuyorsa sebebi hemen hemen her zaman ucunden biri: is_active
kapali, starts_at gelecekte, ends_at gecmiste. Admin'de bu uc alan uc ayri
yerde ve biri yanlis kalirsa uc sessizce 204 doner -- hata mesaji yoktur,
sadece bos slot. Bu komut ucunu birden dogru yazar ve tekrar tekrar
calistirilabilir: ayni title'a sahip kayit varsa gunceller, yoksa olusturur.

    python manage.py seed_extension_ads            # kurar/gunceller
    python manage.py seed_extension_ads --status   # neden gorunmedigini soyler
    python manage.py seed_extension_ads --off      # hepsini pasiflestirir
"""
from django.core.management.base import BaseCommand
from django.utils.timezone import now

from landing.models import ExtensionAd

SITE = "https://vpnsterr.com"

# click_url'e utm eklemiyoruz: istemci kendi kaynagini kendisi ekliyor
# (Android'de utm_source=android_app, eklentide kendi etiketi). Burada sabit
# yazsak iki kaynak birbirine karisirdi.
ADS = [
    {
        "title": "Premium - Annual",
        "image_url": f"{SITE}/static/img/annual.png",
        "click_url": f"{SITE}/pricing/?plan=annual",
        "alt": "VPNsterr Premium annual plan",
        "sponsor": "VPNsterr",
        "weight": 3,
    },
    {
        "title": "Premium - Monthly",
        "image_url": f"{SITE}/static/img/monthly.png",
        "click_url": f"{SITE}/pricing/?plan=monthly",
        "alt": "VPNsterr Premium monthly plan",
        "sponsor": "VPNsterr",
        "weight": 1,
    },
]


class Command(BaseCommand):
    help = "Ucretsiz plandaki tanitim bannerlarini kurar/gunceller."

    def add_arguments(self, parser):
        parser.add_argument("--status", action="store_true",
                            help="Hicbir sey yazmadan neden gorunmediklerini listeler.")
        parser.add_argument("--off", action="store_true",
                            help="Butun reklamlari pasiflestirir.")

    def handle(self, *args, **opts):
        if opts["status"]:
            return self._status()
        if opts["off"]:
            n = ExtensionAd.objects.update(is_active=False)
            self.stdout.write(self.style.WARNING(f"{n} reklam pasiflestirildi."))
            return

        for spec in ADS:
            ad, created = ExtensionAd.objects.update_or_create(
                title=spec["title"],
                defaults={
                    **spec,
                    "media_type": "image",
                    "is_active": True,
                    # Tarihler BILEREK bos: bir zaman penceresi, reklamin
                    # gorunmemesinin en sik ve en fark edilmesi zor sebebi.
                    "starts_at": None,
                    "ends_at": None,
                },
            )
            verb = "olusturuldu" if created else "guncellendi"
            self.stdout.write(self.style.SUCCESS(f"[{verb}] {ad.title}"))

        self._status()

    def _status(self):
        n = now()
        total = ExtensionAd.objects.count()
        self.stdout.write(f"\nVeritabanindaki reklam: {total}")
        if not total:
            self.stdout.write(self.style.ERROR(
                "Hic kayit yok -- /api/extension/ad 204 doner, slot gizlenir."
            ))
            return

        live = 0
        for a in ExtensionAd.objects.all():
            why = []
            if not a.is_active:
                why.append("is_active=False")
            if a.starts_at and a.starts_at > n:
                why.append(f"starts_at gelecekte ({a.starts_at:%Y-%m-%d %H:%M})")
            if a.ends_at and a.ends_at < n:
                why.append(f"ends_at gecmiste ({a.ends_at:%Y-%m-%d %H:%M})")
            if why:
                self.stdout.write(self.style.WARNING(
                    f"  gizli  #{a.pk} {a.title} -> {', '.join(why)}"
                ))
            else:
                live += 1
                self.stdout.write(self.style.SUCCESS(f"  YAYINDA #{a.pk} {a.title}"))

        if live:
            self.stdout.write(self.style.SUCCESS(f"\n{live} reklam yayinda."))
        else:
            self.stdout.write(self.style.ERROR(
                "\nYayinda reklam yok -- uc 204 dondurmeye devam eder."
            ))
