"""Footer'daki tuzel kisilik bilgileri ve Organization JSON-LD.

Bir VPN'de bu kozmetik degil: kullanici butun trafigini emanet ediyor ve
"bunlar kim, nerede kayitli" sorusunun cevabini goremezse guvenmez. Ayrica
bu testler, siteye ASLA girmemesi gereken iki seyi de bekliyor.
"""
import json
import re

from django.conf import settings
from django.test import TestCase


class FooterCompanyDetailsTests(TestCase):
    def setUp(self):
        self.body = self.client.get("/").content.decode()

    def test_it_shows_the_registered_identity(self):
        for needed in (settings.COMPANY_LEGAL_NAME,
                       settings.COMPANY_REG_CODE,
                       settings.COMPANY_DUNS,
                       settings.COMPANY_ADDRESS_LINE,
                       settings.SUPPORT_EMAIL):
            with self.subTest(needed=needed):
                self.assertIn(needed, self.body)

    def test_it_links_the_public_register(self):
        self.assertIn(settings.COMPANY_REGISTRY_URL, self.body)
        self.assertIn("ariregister.rik.ee", self.body)

    def test_legal_name_carries_the_company_form(self):
        # "Sterr Technologies" tek basina tuzel kisiligin adi degil.
        self.assertTrue(settings.COMPANY_LEGAL_NAME.endswith("OÜ"))

    def test_personal_id_code_is_never_published(self):
        """Yonetim kurulu uyesinin isikukood'u sicilde acik olsa bile siteye
        konmaz: gereksiz ve kimlik hirsizligina davetiye."""
        self.assertNotIn("50109180114", self.body)
        # Genel bicim kontrolu: 11 haneli Estonya kimlik numarasi kalibi
        self.assertEqual(re.findall(r"\b[1-6]\d{10}\b", self.body), [])

    def test_founders_personal_email_is_not_published(self):
        self.assertNotIn("ekinsipahi8@gmail.com", self.body)
        self.assertNotIn("ekinsipahi61@gmail.com", self.body)

    def test_it_appears_on_every_page_not_just_home(self):
        for path in ("/pricing/", "/support/", "/faq/"):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                self.assertIn(settings.COMPANY_REG_CODE, body)


class OrganizationSchemaTests(TestCase):
    def _schema(self):
        """Organization düğümü.

        Site geneli JSON-LD artık tek bir @graph olarak basılıyor (Organization
        + WebSite birbirine @id ile bağlı), o yüzden düğümleri düzleştirip
        arıyoruz; eskiden her biri ayrı bir script'ti.
        """
        body = self.client.get("/").content.decode()
        for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>',
                               body, re.S):
            data = json.loads(blob)
            for node in (data["@graph"] if "@graph" in data else [data]):
                if node.get("@type") == "Organization":
                    return node
        self.fail("Organization JSON-LD bulunamadi")

    def test_it_carries_verifiable_identifiers(self):
        org = self._schema()
        values = {i["value"] for i in org["identifier"]}
        self.assertIn(settings.COMPANY_REG_CODE, values)
        self.assertIn(settings.COMPANY_DUNS, values)

    def test_it_carries_a_postal_address(self):
        addr = self._schema()["address"]
        self.assertEqual(addr["@type"], "PostalAddress")
        self.assertEqual(addr["addressCountry"], "EE")
        self.assertEqual(addr["postalCode"], settings.COMPANY_ADDRESS_POSTAL)

    def test_legal_name_matches_the_footer(self):
        self.assertEqual(self._schema()["legalName"], settings.COMPANY_LEGAL_NAME)

    def test_register_entry_is_listed_as_sameas(self):
        self.assertIn(settings.COMPANY_REGISTRY_URL, self._schema()["sameAs"])
