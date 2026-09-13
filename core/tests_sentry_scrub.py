"""core/sentry_scrub.py testleri.

Bu dosyanin varlik sebebi somut: /api/cron/reconcile/?key=<CRON_SECRET>
ucundan gecen bir hata, cron anahtarini Sentry'ye duz metin yaziyordu.
Asagidaki testler o sizintinin geri gelmedigini kanitlar.
"""
from django.test import SimpleTestCase, override_settings

from core import sentry_scrub
from core.sentry_scrub import FILTERED, scrub, scrub_query_string, scrub_url


class QueryStringScrubTests(SimpleTestCase):
    def test_sensitive_names_are_filtered(self):
        for qs in ("key=abc123", "token=abc", "api_key=abc", "X-Cron-Key=abc",
                   "access_token=abc", "code=oauth", "password=abc", "email=a@b.c"):
            with self.subTest(qs=qs):
                self.assertIn(FILTERED, scrub_query_string(qs))
                self.assertNotIn("abc", scrub_query_string(qs).split("=")[-1])

    def test_harmless_params_survive(self):
        # Ayiklama isini imkansiz kilmamak icin zararsizlar aynen kalir.
        self.assertEqual(scrub_query_string("next=/dashboard/&page=2"),
                         "next=/dashboard/&page=2")

    def test_mixed_params_only_filter_the_secret(self):
        self.assertEqual(scrub_query_string("next=/x&key=s3cr3t&page=2"),
                         f"next=/x&key={FILTERED}&page=2")

    def test_empty_and_valueless(self):
        self.assertEqual(scrub_query_string(""), "")
        # "?key" (= yok) parse_qsl ile kaybolurdu; ham bolme korur.
        self.assertEqual(scrub_query_string("key"), "key")


class UrlScrubTests(SimpleTestCase):
    def test_query_is_scrubbed_in_url(self):
        out = scrub_url("https://vpnsterr.com/api/cron/reconcile/?key=s3cr3t")
        self.assertEqual(out, f"https://vpnsterr.com/api/cron/reconcile/?key={FILTERED}")

    def test_password_reset_token_is_stripped_from_path(self):
        # Yol uzerindeki sifirlama token'i hesap ele gecirme araci.
        out = scrub_url("https://vpnsterr.com/password-reset/MQ/set-password-abc123/")
        self.assertEqual(out, f"https://vpnsterr.com/password-reset/{FILTERED}/")

    def test_password_reset_index_page_untouched(self):
        out = scrub_url("https://vpnsterr.com/password-reset/")
        self.assertEqual(out, "https://vpnsterr.com/password-reset/")

    def test_plain_url_untouched(self):
        self.assertEqual(scrub_url("https://vpnsterr.com/pricing/"),
                         "https://vpnsterr.com/pricing/")


@override_settings(CRON_SECRET="TOP_SECRET_CRON_VALUE_123",
                   EXTENSION_SHARED_SECRET="TOP_SECRET_EXT_VALUE_456")
class EventScrubTests(SimpleTestCase):
    def setUp(self):
        sentry_scrub._secret_values = None  # onbellegi sifirla

    def tearDown(self):
        sentry_scrub._secret_values = None

    def test_request_query_string_and_url(self):
        event = scrub({"request": {
            "url": "https://vpnsterr.com/api/cron/reconcile/",
            "query_string": "key=TOP_SECRET_CRON_VALUE_123",
        }})
        self.assertEqual(event["request"]["query_string"], f"key={FILTERED}")

    def test_secret_in_a_log_message_is_redacted(self):
        # Isim tabanli filtre buraya bakmaz; deger tabanli ag yakalamali.
        event = scrub({"logentry": {
            "formatted": "cron rejected: given=TOP_SECRET_CRON_VALUE_123",
        }})
        self.assertNotIn("TOP_SECRET_CRON_VALUE_123", str(event))
        self.assertIn(FILTERED, event["logentry"]["formatted"])

    def test_secret_in_an_exception_value_is_redacted(self):
        event = scrub({"exception": {"values": [
            {"type": "ValueError", "value": "bad secret TOP_SECRET_EXT_VALUE_456"},
        ]}})
        self.assertNotIn("TOP_SECRET_EXT_VALUE_456", str(event))

    def test_breadcrumb_urls_are_scrubbed(self):
        event = scrub({"breadcrumbs": {"values": [
            {"data": {"url": "https://vpnsterr.com/x/?token=abc"}},
        ]}})
        self.assertIn(FILTERED, event["breadcrumbs"]["values"][0]["data"]["url"])

    def test_short_settings_values_are_not_treated_as_secrets(self):
        # 8 karakterin altindaki bir deger her yerde eslesip olayi okunmaz
        # hale getirirdi; sir sayilmamali.
        with override_settings(CRON_SECRET="ab"):
            sentry_scrub._secret_values = None
            event = scrub({"logentry": {"formatted": "abcabc normal mesaj"}})
            self.assertEqual(event["logentry"]["formatted"], "abcabc normal mesaj")

    def test_scrub_never_raises(self):
        # Izleme araci uygulamayi kor edemez.
        self.assertIsNone(scrub(None))
        self.assertEqual(scrub({"request": "not-a-dict"})["request"], "not-a-dict")
        self.assertEqual(scrub({"breadcrumbs": 5})["breadcrumbs"], 5)

    def test_unserialisable_event_survives(self):
        event = {"extra": {"obj": object()}, "request": {"query_string": "key=x"}}
        out = scrub(event)
        self.assertEqual(out["request"]["query_string"], f"key={FILTERED}")


class PiiHeaderScrubTests(SimpleTestCase):
    """Canlida gorulen gercek olay Cf-Connecting-Ip ve True-Client-Ip
    basliklarinda ziyaretcinin duz IP'sini Sentry'ye tasiyordu."""

    def test_ip_headers_are_filtered_dict_form(self):
        event = scrub({"request": {"headers": {
            "Cf-Connecting-Ip": "167.71.10.9",
            "True-Client-Ip": "167.71.10.9",
            "X-Forwarded-For": "167.71.10.9, 172.71.0.1",
            "Cf-Ipcountry": "NL",
            "User-Agent": "Mozilla/5.0",
        }}})
        h = event["request"]["headers"]
        self.assertEqual(h["Cf-Connecting-Ip"], FILTERED)
        self.assertEqual(h["True-Client-Ip"], FILTERED)
        self.assertEqual(h["X-Forwarded-For"], FILTERED)
        # Ulke ve tarayici ayiklama icin lazim, kimliklendirmez: kalir.
        self.assertEqual(h["Cf-Ipcountry"], "NL")
        self.assertEqual(h["User-Agent"], "Mozilla/5.0")
        self.assertNotIn("167.71.10.9", str(event))

    def test_ip_headers_are_filtered_list_form(self):
        event = scrub({"request": {"headers": [
            ["Cf-Connecting-Ip", "167.71.10.9"], ["Host", "vpnsterr.com"],
        ]}})
        self.assertNotIn("167.71.10.9", str(event))
        self.assertIn(["Host", "vpnsterr.com"], event["request"]["headers"])

    def test_referer_query_is_scrubbed(self):
        event = scrub({"request": {"headers": {
            "Referer": "https://vpnsterr.com/x/?token=abc123",
        }}})
        self.assertEqual(event["request"]["headers"]["Referer"],
                         f"https://vpnsterr.com/x/?token={FILTERED}")

    def test_remote_addr_in_env_is_filtered(self):
        event = scrub({"request": {"env": {"REMOTE_ADDR": "167.71.10.9",
                                           "SERVER_NAME": "vpnsterr.com"}}})
        self.assertEqual(event["request"]["env"]["REMOTE_ADDR"], FILTERED)
        self.assertEqual(event["request"]["env"]["SERVER_NAME"], "vpnsterr.com")

    def test_user_ip_is_filtered_even_if_pii_flag_flips(self):
        event = scrub({"user": {"id": "1", "ip_address": "167.71.10.9"}})
        self.assertEqual(event["user"]["ip_address"], FILTERED)

    def test_missing_headers_do_not_crash(self):
        self.assertEqual(scrub({"request": {}})["request"], {})
        self.assertEqual(scrub({"request": {"headers": None}})["request"]["headers"], None)
