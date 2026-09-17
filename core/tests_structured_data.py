"""Sayfalardaki JSON-LD yapısal verisi.

Yapısal veri sessizce bozulur: bir virgül hatası ya da ikinci bir
Organization düğümü sayfada hiçbir belirti vermez, sadece arama motoru
onu yok sayar ya da iki ayrı kuruluş sanar. Bu yüzden testle tutuluyor.

Footer'daki tüzel kimlikle (sicil kodu, D-U-N-S, adres, tüzel ad) yapısal
verinin AYNI kaynaktan gelmesi de burada doğrulanıyor — ikisi ayrışırsa
"bunlar kim" sorusuna site iki farklı cevap vermiş olur.
"""
import json
import re

from django.conf import settings
from django.test import TestCase

BLOB = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

# Bu testin kapsadığı sayfalar. privacy/terms/refund/acceptable-use şu an
# başka bir ajanın üzerinde çalıştığı dosyalar; onlar hâlâ eski tüzel adı
# ("OÜ" olmadan) gömüyor — oraya dokunmuyoruz.
PAGES = ["/", "/pricing/", "/vpn-extension/", "/free-vpn/", "/support/",
         "/blog/", "/faq/", "/best-vpn/", "/changelog/"]


def nodes(body):
    """Sayfadaki tüm JSON-LD düğümleri (@graph düzleştirilmiş)."""
    out = []
    for blob in BLOB.findall(body):
        data = json.loads(blob)          # bozuksa test burada düşer
        out.extend(data["@graph"] if "@graph" in data else [data])
    return out


class EveryPageParsesTests(TestCase):
    def test_all_json_ld_is_valid_json(self):
        for path in PAGES:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                self.assertTrue(nodes(r.content.decode()),
                                "sayfada hiç JSON-LD yok")

    def test_exactly_one_organization_per_page(self):
        """İkinci bir Organization = arama motoru için ikinci bir şirket.

        Eskiden /pricing/ kendi kopyasını basıyordu ve @id'si
        request.build_absolute_uri'den türediği için ".../pricing/#org"
        oluyordu — global düğümden kopuk, ayrı bir varlık.
        """
        for path in PAGES:
            with self.subTest(path=path):
                orgs = [n for n in nodes(self.client.get(path).content.decode())
                        if n.get("@type") == "Organization"]
                self.assertEqual(len(orgs), 1, f"{len(orgs)} Organization düğümü")


class OrganizationMatchesTheFooterTests(TestCase):
    def setUp(self):
        self.org = next(n for n in nodes(self.client.get("/").content.decode())
                        if n.get("@type") == "Organization")

    def test_identity_fields_come_from_the_same_source_as_the_footer(self):
        self.assertEqual(self.org["legalName"], settings.COMPANY_LEGAL_NAME)
        ids = {i["value"] for i in self.org["identifier"]}
        self.assertIn(settings.COMPANY_REG_CODE, ids)
        self.assertIn(settings.COMPANY_DUNS, ids)
        self.assertEqual(self.org["address"]["postalCode"],
                         settings.COMPANY_ADDRESS_POSTAL)
        self.assertEqual(self.org["address"]["addressCountry"], "EE")

    def test_public_register_is_listed_as_sameas(self):
        self.assertIn(settings.COMPANY_REGISTRY_URL, self.org["sameAs"])

    def test_the_id_is_absolute_and_environment_independent(self):
        """@id SITE_URL'den türeseydi dev'de 127.0.0.1 olurdu ve düğümler
        birbirine bağlanmazdı."""
        self.assertEqual(self.org["@id"], "https://vpnsterr.com/#org")
        self.assertEqual(self.org["url"], "https://vpnsterr.com")
        self.assertNotIn("127.0.0.1", json.dumps(self.org))

    def test_legal_name_carries_the_company_form(self):
        self.assertTrue(self.org["legalName"].endswith("OÜ"))


class NodesAreLinkedTests(TestCase):
    ORG_ID = "https://vpnsterr.com/#org"

    def _nodes(self, path):
        return nodes(self.client.get(path).content.decode())

    def test_website_points_at_the_organization(self):
        site = next(n for n in self._nodes("/") if n.get("@type") == "WebSite")
        self.assertEqual(site["publisher"]["@id"], self.ORG_ID)

    def test_the_product_is_attributed_to_the_company(self):
        prod = next(n for n in self._nodes("/")
                    if "Product" in (n.get("@type") or []))
        self.assertEqual(prod["provider"]["@id"], self.ORG_ID)

    def test_the_free_extension_names_its_seller(self):
        app = next(n for n in self._nodes("/vpn-extension/")
                   if n.get("@type") == "SoftwareApplication")
        self.assertEqual(app["provider"]["@id"], self.ORG_ID)
        self.assertEqual(app["offers"]["seller"]["@id"], self.ORG_ID)

    def test_blog_and_support_publishers_resolve_to_the_same_company(self):
        for path, wanted in (("/blog/", "Blog"), ("/support/", "ContactPage")):
            with self.subTest(path=path):
                node = next(n for n in self._nodes(path)
                            if n.get("@type") == wanted)
                self.assertEqual(node["publisher"]["@id"], self.ORG_ID)
                self.assertEqual(node["publisher"]["name"],
                                 settings.COMPANY_LEGAL_NAME)

    def test_no_page_in_scope_still_uses_the_old_bare_legal_name(self):
        """Sicildeki ad "Sterr Technologies OÜ"; "OÜ"suz hali başka bir
        tüzel kişiliğe işaret eder."""
        for path in PAGES:
            with self.subTest(path=path):
                blob = json.dumps(self._nodes(path), ensure_ascii=False)
                self.assertNotIn('"Sterr Technologies"', blob)
