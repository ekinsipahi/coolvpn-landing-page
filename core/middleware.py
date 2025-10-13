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
