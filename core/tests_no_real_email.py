"""Testler gerçek e-posta göndermemeli.

OLAN ŞU: test suite'i her koştuğunda kayıt akışı çalışıyor ve
send_welcome_email uydurma adreslere (eski@t.test, insan@t.test) GERÇEK
Resend maili atıyordu. ".test" var olmayan bir TLD, dolayısıyla hepsi
bounce oldu — ve bounce'lar gönderim itibarını düşürüp gerçek müşterinin
mailini spam'e düşürebilir.

Django'nun test koşucusu EMAIL_BACKEND'i locmem'e çevirir ama bu bizi
KURTARMAZ: mailer, RESEND_API_KEY doluysa doğrudan HTTP atıyor ve Django
backend'ini hiç görmüyor. Bu yüzden anahtar test modunda boşaltılıyor;
aşağıdakiler o kapının kapalı kaldığını doğruluyor.
"""
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from landing.helpers import mailer


class NoRealEmailDuringTestsTests(SimpleTestCase):
    def test_resend_key_is_blank_while_testing(self):
        self.assertEqual(settings.RESEND_API_KEY, "",
                         "test modunda RESEND_API_KEY dolu — gerçek mail gider")

    def test_email_backend_is_locmem(self):
        self.assertIn("locmem", settings.EMAIL_BACKEND)

    def test_send_now_never_touches_the_network(self):
        """Anahtar boşken mailer HTTP katmanına hiç inmemeli."""
        with mock.patch.object(mailer.urllib.request, "urlopen") as net:
            mailer._send_now("kimse@t.test", "konu", "<p>gövde</p>", "gövde")
        net.assert_not_called()

    def test_the_whole_welcome_flow_stays_offline(self):
        from django.contrib.auth import get_user_model

        user = get_user_model()(username="offline", email="offline@t.test")
        sent = []
        # send_email_bg daemon thread açıyor; senkron yakalayıp içeriği
        # kontrol ediyoruz — asıl mesele ağa çıkılmaması.
        with mock.patch.object(mailer, "send_email_bg",
                               side_effect=lambda *a, **k: sent.append(a)), \
             mock.patch.object(mailer.urllib.request, "urlopen") as net:
            mailer.send_welcome_email(user)
        net.assert_not_called()
        self.assertTrue(sent, "mail hazırlanmadı — akış bozulmuş olabilir")
