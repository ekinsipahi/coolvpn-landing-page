"""Sentry'ye giden olaylardan sırları temizler.

Neden gerekli: Sentry'nin kendi varsayılan filtresi Authorization ve Cookie
başlıklarını temizler, ama URL'in QUERY STRING'ine dokunmaz. Bu projede
sırlar query string'de dolaşıyor:

    /api/cron/reconcile/?key=<CRON_SECRET>
    /accounts/google/login/callback/?code=<OAuth kodu>
    /password-reset/<uidb64>/<token>/          (query değil, YOL üzerinde)

Bir 500 ya da WARNING bu uçlardan geçtiği anda o sır üçüncü bir servise
düz metin olarak yazılır ve orada aylarca durur. "Zero logs" diyen bir
üründe bu kabul edilemez, üstelik cron key'i ele geçiren biri abonelik
mutabakatını istediği gibi tetikleyebilir.

İki katman:
  1) İsim tabanlı — adında key/token/secret/... geçen parametre değerleri
     ve ziyaretçi IP'sini taşıyan başlıklar (Cf-Connecting-Ip vb.).
  2) Değer tabanlı — settings'te duran GERÇEK sırların birebir metni,
     olayın neresinde geçerse geçsin (log satırı, exception mesajı,
     breadcrumb, stack trace local'ı) silinir. Birinci katman kaçırırsa
     ağ diye bu var.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit, urlunsplit

FILTERED = "[Filtered]"

# Adında bunlardan biri geçen query parametresinin DEĞERİ gizlenir.
_SENSITIVE_PARAM_PARTS = (
    "key", "token", "secret", "pass", "auth", "code", "sig", "sess",
    "nonce", "otp", "hash", "credential", "email", "card", "cvc",
)

# Ziyaretçinin GERÇEK IP'sini taşıyan başlıklar. send_default_pii=False
# bunları temizlemez — Sentry yalnızca Authorization/Cookie gibi bilinen
# kimlik başlıklarını filtreler. Cloudflare + Render arkasında duran bu
# başlıklar canlıda Sentry'ye düz IP yazıyordu; "no-logs" diyen bir VPN'de
# bu, sözün kendisiyle çelişir. Cf-Ipcountry (yalnızca ülke) bilerek
# bırakıldı: kimliklendirmez ama bölgesel hataları ayıklamaya yarar.
_PII_HEADERS = frozenset({
    "cf-connecting-ip", "cf-connecting-o2o", "true-client-ip",
    "x-forwarded-for", "x-real-ip", "x-client-ip", "x-cluster-client-ip",
    "fastly-client-ip", "forwarded", "remote-addr",
})

# Değeri URL olan ve içinde sır taşıyabilen başlıklar.
_URL_HEADERS = frozenset({"referer", "referrer", "origin", "location"})

# Yolun tamamı gizli sayılan uçlar: /password-reset/<uidb64>/<token>/
# adresindeki token TEK KULLANIMLIK ama hâlâ geçerli bir hesap ele
# geçirme aracı; Sentry'ye düşmemeli.
_SENSITIVE_PATH_PREFIXES = ("/password-reset/",)

# settings'ten okunacak, birebir metin olarak aranacak sır isimleri.
_SECRET_SETTINGS = (
    "CRON_SECRET", "EXTENSION_SHARED_SECRET", "SECRET_KEY",
    "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "NOWPAYMENTS_API_KEY",
    "NOWPAYMENTS_IPN_SECRET", "RESEND_API_KEY", "ANTHROPIC_API_KEY",
    "SENTRY_AUTH_TOKEN", "GOOGLE_CLIENT_SECRET",
)

_secret_values: list[str] | None = None


def _known_secrets() -> list[str]:
    """settings'teki gerçek sır değerleri. Bir kez okunur, sonra önbellek."""
    global _secret_values
    if _secret_values is None:
        from django.conf import settings
        vals = set()
        for name in _SECRET_SETTINGS:
            v = getattr(settings, name, "") or ""
            v = str(v).strip()
            # Kısa/boş değerler tesadüfen her yerde eşleşip olayı okunmaz
            # hale getirir; 8 karakterin altını sır saymıyoruz.
            if len(v) >= 8:
                vals.add(v)
        _secret_values = sorted(vals, key=len, reverse=True)
    return _secret_values


def _is_sensitive_param(name: str) -> bool:
    n = name.lower()
    return any(part in n for part in _SENSITIVE_PARAM_PARTS)


def scrub_query_string(qs: str) -> str:
    """key=abc&next=/x -> key=[Filtered]&next=/x

    parse_qsl kullanmıyoruz: o, tanımadığı parçaları sessizce atar ve
    imzasız/boş parametreler kaybolur. Ham metni bölmek daha sadık.
    """
    if not qs:
        return qs
    out = []
    for pair in qs.split("&"):
        if not pair:
            continue
        name, sep, _value = pair.partition("=")
        if sep and _is_sensitive_param(name):
            out.append(f"{name}={FILTERED}")
        else:
            out.append(pair)
    return "&".join(out)


def scrub_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    path = parts.path
    for prefix in _SENSITIVE_PATH_PREFIXES:
        if path.startswith(prefix):
            rest = path[len(prefix):].strip("/")
            if rest:
                path = prefix + FILTERED + "/"
            break
    return urlunsplit((parts.scheme, parts.netloc, path,
                       scrub_query_string(parts.query), parts.fragment))


def _scrub_headers(req: dict) -> None:
    """IP taşıyan başlıkları siler, URL taşıyanların query'sini temizler.

    Başlıklar SDK'da dict, Sentry API'sinde [ [ad, değer], ... ] listesi
    olarak görünür; ikisini de karşılıyoruz.
    """
    headers = req.get("headers")
    if isinstance(headers, dict):
        for name in list(headers):
            low = str(name).lower()
            if low in _PII_HEADERS:
                headers[name] = FILTERED
            elif low in _URL_HEADERS and isinstance(headers[name], str):
                headers[name] = scrub_url(headers[name])
    elif isinstance(headers, list):
        for pair in headers:
            if isinstance(pair, list) and len(pair) == 2:
                low = str(pair[0]).lower()
                if low in _PII_HEADERS:
                    pair[1] = FILTERED
                elif low in _URL_HEADERS and isinstance(pair[1], str):
                    pair[1] = scrub_url(pair[1])


def _scrub_request(event: dict) -> None:
    req = event.get("request")
    if not isinstance(req, dict):
        return
    if isinstance(req.get("query_string"), str):
        req["query_string"] = scrub_query_string(req["query_string"])
    if isinstance(req.get("url"), str):
        req["url"] = scrub_url(req["url"])
    _scrub_headers(req)
    env = req.get("env")
    if isinstance(env, dict) and "REMOTE_ADDR" in env:
        env["REMOTE_ADDR"] = FILTERED


def _scrub_user_ip(event: dict) -> None:
    """user.ip_address'i her ihtimale karşı boşalt.

    send_default_pii=False zaten doldurmuyor ama ayar yanlışlıkla açılırsa
    bu ağ tutar; kullanıcının IP'si tek bir bayrağa bağlı kalmasın.
    """
    user = event.get("user")
    if isinstance(user, dict) and user.get("ip_address"):
        user["ip_address"] = FILTERED


def _scrub_breadcrumbs(event: dict) -> None:
    crumbs = event.get("breadcrumbs")
    if isinstance(crumbs, dict):
        crumbs = crumbs.get("values")
    if not isinstance(crumbs, list):
        return
    for crumb in crumbs:
        if not isinstance(crumb, dict):
            continue
        if isinstance(crumb.get("message"), str):
            crumb["message"] = scrub_url(crumb["message"]) if "://" in crumb["message"] else crumb["message"]
        data = crumb.get("data")
        if isinstance(data, dict):
            for k in ("url", "http.url", "path"):
                if isinstance(data.get(k), str):
                    data[k] = scrub_url(data[k])


def _redact_known_secrets(event: dict) -> dict:
    """Olayın HER yerinde geçen gerçek sır metinlerini siler.

    İsim tabanlı filtre yalnızca query string'e bakar; sır bir log
    satırında ya da exception mesajında da geçebilir. Bu, o durum için
    son emniyet: olayı JSON'a çevirip birebir arıyoruz.
    """
    secrets = _known_secrets()
    if not secrets:
        return event
    try:
        blob = json.dumps(event)
    except (TypeError, ValueError):
        return event  # serileşmiyorsa dokunmuyoruz, olay yine de gider
    hit = False
    for secret in secrets:
        if secret in blob:
            blob = blob.replace(secret, FILTERED)
            hit = True
    if not hit:
        return event
    try:
        return json.loads(blob)
    except ValueError:
        return event


def scrub(event, hint=None):
    """sentry_sdk before_send / before_send_transaction kancası.

    Asla istisna sızdırmaz: buradaki bir hata, izleme aracının uygulamayı
    kör etmesi demek olurdu.
    """
    try:
        if not isinstance(event, dict):
            return event
        _scrub_request(event)
        _scrub_user_ip(event)
        _scrub_breadcrumbs(event)
        return _redact_known_secrets(event)
    except Exception:  # noqa: BLE001
        return event
