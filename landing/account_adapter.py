"""allauth adaptörü — kullanılmayan kayıt sayfasını kapatır.

/accounts/signup/ canlıda 200 dönüyordu ama siteden HİÇBİR yer oraya link
vermiyor: gerçek akış /auth/email-upsert-login/. Yani orası yalnızca botların
bulduğu, captcha'sız bir yan kapıydı — kayıt formuna Turnstile koyup bunu
açık bırakmak korumayı anlamsız kılardı.

URL'leri kaldırmak yerine adaptörle kapatıyoruz: allauth.urls sosyal giriş
geri-çağrılarını da taşıyor, onları kırmak istemiyoruz.
"""
from allauth.account.adapter import DefaultAccountAdapter


class ClosedSignupAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False
