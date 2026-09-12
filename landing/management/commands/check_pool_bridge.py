"""Site <-> havuz premium köprüsünü uçtan uca doğrular.

Bu komut, 2026-09'da günlerce süren "giriş yaptım ama premium gelmiyor"
hatasının teşhisi için yazıldı. O hatada site premium diyordu, havuz free
diyordu ve hiçbir taraf sebebini söylemiyordu; asıl sebep iki tarafın FARKLI
paylaşılan sır ile çalışmasıydı.

    python manage.py check_pool_bridge
    python manage.py check_pool_bridge --email someone@example.com

Sırrın kendisini asla yazdırmaz; yalnızca sha256'sının ilk 12 hanesini
("parmak izi") karşılaştırır.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

POOL_BASE = "https://pool.vpnsterr.com"
UA = "vpnsterr-bridge-check/1.0"


def _fp(secret: str) -> str:
    if not secret:
        return "unset"
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def _get(url: str, payload: dict | None = None, timeout: int = 20):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"User-Agent": UA}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class Command(BaseCommand):
    help = "Site ile havuzun premium köprüsünü test eder (paylaşılan sır + tier)."

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Test edilecek premium kullanıcı")
        parser.add_argument("--pool", default=POOL_BASE, help="Havuz adresi")

    def handle(self, *args, **opts):
        ok = self.style.SUCCESS
        bad = self.style.ERROR
        warn = self.style.WARNING
        pool = opts["pool"].rstrip("/")

        site_secret = getattr(settings, "EXTENSION_SHARED_SECRET", "") or ""
        site_fp = _fp(site_secret)
        self.stdout.write(f"site  EXTENSION_SHARED_SECRET  fp={site_fp} (uzunluk {len(site_secret)})")
        if not site_secret:
            self.stdout.write(bad("HATA: sitede EXTENSION_SHARED_SECRET boş."))
            return

        # 1) Havuzun parmak izi
        pool_fp = None
        try:
            health = _get(f"{pool}/v1/health")
            pool_fp = health.get("extension_secret_fp")
            self.stdout.write(f"havuz extension_secret       fp={pool_fp or '(bildirmiyor)'} "
                              f"(sürüm {health.get('version')})")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self.stdout.write(bad(f"havuza ulaşılamadı: {exc}"))
            return

        if pool_fp is None:
            self.stdout.write(warn(
                "Havuz parmak izi bildirmiyor — eski sürüm çalışıyor. "
                "Havuzu güncelleyince bu satır dolacak."))
        elif pool_fp != site_fp:
            self.stdout.write(bad(
                "\n>>> SIRLAR FARKLI. Premium bu yüzden çalışmıyor.\n"
                "    Havuz sunucusunda PROXYHUNTER_EXTENSION_SECRET (ya da config'teki\n"
                "    extension_secret) sitenin .env'indeki EXTENSION_SHARED_SECRET ile\n"
                "    BİREBİR aynı olmalı; sonra havuzu yeniden başlat."))
        else:
            self.stdout.write(ok(">>> Parmak izleri eşleşiyor."))

        # 2) Gerçek bir premium kullanıcıyla uçtan uca dene
        from landing.views import _mint_account_token, _user_tier_and_exp

        User = get_user_model()
        user = None
        if opts.get("email"):
            user = User.objects.filter(email__iexact=opts["email"]).first()
            if user is None:
                self.stdout.write(bad(f"kullanıcı bulunamadı: {opts['email']}"))
                return
        else:
            for candidate in User.objects.filter(subscriptions__isnull=False).distinct():
                if _user_tier_and_exp(candidate)[0] == "premium":
                    user = candidate
                    break
        if user is None:
            self.stdout.write(warn("Premium kullanıcı yok — uçtan uca test atlandı."))
            return

        tier, exp, _sub = _user_tier_and_exp(user)
        device = user.devices.filter(is_active=True).first()
        device_id = device.client_uuid if device else "bridge-check-device"
        token = _mint_account_token(user, device_id, tier, exp)
        self.stdout.write(f"\ntest kullanıcısı: {user.email} | sitenin dediği tier: {tier}")

        try:
            resp = _get(f"{pool}/api/extension/session",
                        {"device_id": device_id, "account_token": token})
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self.stdout.write(bad(f"havuz oturum isteği başarısız: {exc}"))
            return

        pool_tier = resp.get("tier")
        status = resp.get("account_status", "(bildirmiyor)")
        self.stdout.write(f"havuzun dediği tier: {pool_tier} | account_status: {status}")

        if tier == "premium" and pool_tier == "premium":
            self.stdout.write(ok("\n>>> KÖPRÜ SAĞLAM: premium uçtan uca çalışıyor."))
        elif tier == "premium":
            self.stdout.write(bad(
                f"\n>>> KÖPRÜ BOZUK: site premium diyor, havuz {pool_tier} diyor."))
            hint = {
                "bad_signature_or_expired":
                    "Paylaşılan sır uyuşmuyor (ya da token süresi dolmuş). Yukarıdaki fp'leri karşılaştır.",
                "device_mismatch":
                    "Token başka bir cihaz için üretilmiş; eklenti farklı device_id gönderiyor.",
                "not_premium":
                    "Token 'free' olarak imzalanmış; site abonelik görmüyor olabilir.",
                "none":
                    "Havuza account_token hiç ulaşmamış.",
            }.get(status)
            if hint:
                self.stdout.write(bad(f"    Sebep: {hint}"))
