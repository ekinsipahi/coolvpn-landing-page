"""Cloudflare Turnstile — hesap açma/giriş için bot doğrulaması.

NEDEN TURNSTILE, reCAPTCHA DEĞİL: burası "zero-log" iddiasıyla satılan bir
VPN. Google reCAPTCHA her ziyaretçiyi Google'a tanıtır ve ziyaretçi verisini
reklam ekosistemine bağlar; bunu gizlilik ürününün kayıt formuna koymak
sözün kendisiyle çelişirdi. Turnstile ücretsiz, çerez kullanmıyor ve site
zaten Cloudflare arkasında.

NEDEN LAZIM: 2026-09-09'da tek kişi 7 dakikada 16 farklı kartla denedi.
Stripe Radar (Standard) TARANAN HER ÖDEME İÇİN 0.05 EUR yazıyor — o gün
0.80 EUR fatura çıktı. Botu checkout'ta durdurmak geç; hesabı açarken
durdurmak gerekiyor.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TIMEOUT = 6


def enabled() -> bool:
    """Anahtarlar tanımlı değilse doğrulama yapılmaz.

    Deploy, anahtarlar panele girilmeden önce çıkarsa kimse kaydolamaz
    hale gelmesin diye kapalıyken sessizce geçiyoruz — ama bu durum
    ``manage.py check_bot_shield`` ile görünür.
    """
    return bool(getattr(settings, "TURNSTILE_SECRET_KEY", ""))


def verify(token: str, remote_ip: str = "") -> bool:
    """Turnstile jetonunu Cloudflare'a doğrulatır.

    AĞ HATASINDA GEÇİRMİYORUZ (fail-closed). Açık bırakan bir captcha
    captcha değildir: Cloudflare'a ulaşılamadığı anda bot seli geri gelir
    ve faturayı Radar yazar. Kısa bir Cloudflare kesintisinde kayıt durur;
    bu, kontrolsüz bot trafiğinden iyidir ve hata Sentry'ye düşer.
    """
    if not enabled():
        return True
    token = (token or "").strip()
    if not token:
        return False

    data = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    req = urllib.request.Request(
        _VERIFY_URL, data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "vpnsterr-turnstile/1.0 (+https://vpnsterr.com)"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            body = json.loads(r.read().decode("utf-8") or "{}")
    except Exception as exc:  # noqa: BLE001
        log.warning("turnstile: doğrulama yapılamadı (%s) — istek reddedildi", exc)
        return False
    if not body.get("success"):
        log.info("turnstile: jeton reddedildi %s", body.get("error-codes"))
        return False
    return True
