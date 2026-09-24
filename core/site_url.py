"""Dışarı verilen mutlak adreslerin türetimi.

Ayrı bir modül çünkü bu mantık bir kere yanlış çalıştığında sonuç sessiz ve
pahalı oluyor: 07.09.2026–23.09.2026 arasında Render'da ``SITE_URL`` env'i
tanımlı olmadığı için ``settings.SITE_URL`` ``http://127.0.0.1:8000``
varsayılanına düştü. Bu değer e-posta linklerini, Stripe checkout
success/cancel adreslerini, billing portal dönüş adresini, NOWPayments IPN
adresini ve blog canonical'ını besliyor — hepsi birden müşteriye ölü link
olarak gitti.

Kural basit: üretimde loopback bir adres dışarı çıkamaz. Mantık settings
içinde gömülü kalsaydı test edilemezdi (settings import anında bir kez
değerlenir), o yüzden saf fonksiyonlar halinde burada duruyor.
"""

from urllib.parse import urlsplit

# Boş string de listede: hostname'i olmayan bir değer ("/pricing", "vpnsterr.com"
# gibi şemasız girdiler) mutlak adres olarak kullanılamaz, güvenilmez sayılır.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "0.0.0.0", "::1", ""})


def is_loopback(url: str) -> bool:
    """URL yerel makineyi mi gösteriyor (ya da mutlak adres değil mi)?"""
    try:
        return (urlsplit(url or "").hostname or "") in LOOPBACK_HOSTS
    except ValueError:
        # Bozuk URL'i geçerli saymaktansa reddet.
        return True


def _public(canonical_host: str) -> str:
    return f"https://{(canonical_host or 'vpnsterr.com').strip().strip('/')}"


def resolve_site_url(env_value: str, canonical_host: str, *, debug: bool) -> str:
    """Bu sunucunun dışarıdan erişilen kök adresi.

    Dev'de loopback'e izin var (yerel akışlar çalışsın diye). Üretimde yok:
    env boşsa da, dev ``.env``'i yanlışlıkla kopyalanmışsa da canonical
    host'a sabitlenir.
    """
    value = (env_value or "").strip().rstrip("/")
    if value and not (is_loopback(value) and not debug):
        return value
    return _public(canonical_host)


def resolve_email_base_url(env_value: str, canonical_host: str) -> str:
    """E-posta gövdesindeki linklerin tabanı.

    ``resolve_site_url``'den farklı olarak DEBUG'a bakmaz: alıcı hiçbir zaman
    bu makinede değil, dolayısıyla loopback bir link dev'de de anlamsız.
    Üstelik mailer Resend'e doğrudan POST attığı için ``EMAIL_BACKEND``'i
    atlar — dev sunucusundan da gerçek mail çıkabiliyor.
    """
    value = (env_value or "").strip().rstrip("/")
    if value and not is_loopback(value):
        return value
    return _public(canonical_host)
