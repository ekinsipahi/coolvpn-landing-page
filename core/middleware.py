# core/middleware.py
from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class DomainRedirectMiddleware:
    """
    Eski domainleri (coolvpn.app vb.) kalıcı 301 ile vpnsterr.com'a taşır.
    Path + querystring korunur; Google "Change of Address" bu 301'leri ister.
    Hangi hostların yönlendirileceği .env'deki OLD_HOSTS'tan gelir.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.canonical = getattr(settings, "CANONICAL_HOST", "vpnsterr.com")
        self.old_hosts = {
            h.strip().lower()
            for h in getattr(settings, "OLD_HOSTS", [])
            if h.strip()
        }

    def __call__(self, request):
        host = (request.get_host() or "").split(":")[0].lower()
        if host in self.old_hosts:
            return HttpResponsePermanentRedirect(
                f"https://{self.canonical}{request.get_full_path()}"
            )
        return self.get_response(request)


# core/middleware.py
class CoopAllowPopupsMiddleware:
    """
    FedCM kapalıyken GIS popup/redirect akışı için gerekli:
    İlgili path'lerde COOP'u 'same-origin-allow-popups' yapar.
    """
    PATH_PREFIXES = (
        "/payments",                  # senin checkout sayfan
        "/checkout",                  # varsa
        "/accounts/google/",          # django-allauth default Google yolları
        "/auth/google/",              # senin custom finish/start uçların varsa
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resp = self.get_response(request)
        path = request.path or ""
        if any(path.startswith(p) for p in self.PATH_PREFIXES):
            # kritik header (popup iletişimini bozma)
            resp["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
            # COEP kullanıyorsan (örn. require-corp), checkout'ta kapat:
            # resp["Cross-Origin-Embedder-Policy"] = "unsafe-none"
        return resp
