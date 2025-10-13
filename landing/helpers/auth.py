from django.conf import settings

def pick_backend() -> str:
    """
    Birden fazla AUTHENTICATION_BACKENDS varsa login() için birini seç.
    Önce allauth backend'i, sonra ModelBackend; bulamazsa ilkini döndürür.
    """
    backends = getattr(settings, "AUTHENTICATION_BACKENDS", [])
    for b in backends:
        if b.endswith("allauth.account.auth_backends.AuthenticationBackend"):
            return b
    for b in backends:
        if b.endswith("django.contrib.auth.backends.ModelBackend"):
            return b
    return backends[0] if backends else "django.contrib.auth.backends.ModelBackend"
