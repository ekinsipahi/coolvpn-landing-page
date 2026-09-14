"""Hicbir .env sirri git'e girmemeli.

Bu depo GitHub'da HERKESE ACIK. Bir sirrin takipli bir dosyaya kazara
yazilmasi, onu yayinlamak demek -- ve git gecmisinden silmek, herkesin
kopyaladigi bir seyi geri almaya calismak oldugu icin gec kalinmis olur.
Tek savunma, sirrin oraya HIC girmemesi.

Test .env'i okur (yoksa atlar, CI'da .env olmaz) ve adi sir gibi duran
her degiskenin degerini takipli dosyalarda arar. Yakalarsa hangi dosya
oldugunu soyler.
"""
import re
import subprocess

from django.conf import settings
from django.test import SimpleTestCase

# Adinda bunlardan biri gecen degisken "sir" sayilir.
SECRETISH = re.compile(
    r"(SECRET|KEY|TOKEN|PASSWORD|PASS|DSN|CREDENTIAL|PRIVATE|WEBHOOK|IPN|SALT|SIGNATURE)",
    re.I)

# Adi sir gibi dursa da herkese acik olmasi NORMAL olanlar.
PUBLIC_BY_DESIGN = {
    "GOOGLE_CLIENT_ID",      # OAuth istemci kimligi zaten tarayiciya gider
    "STRIPE_PUBLISH_KEY",    # "publishable" — adi ustunde
    "STRIPE_PUBLISHABLE_KEY",
    "GA_MEASUREMENT_ID",
}


def _env_secrets(path):
    out = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        # 12 karakterin altini aramak anlamsiz: kisa degerler her yerde
        # tesaduffen eslesir ve testi gurultuye bogar.
        if len(value) >= 12 and SECRETISH.search(name) and name not in PUBLIC_BY_DESIGN:
            out[name] = value
    return out


class NoSecretInTrackedFilesTests(SimpleTestCase):
    def test_no_env_secret_appears_in_a_tracked_file(self):
        env_path = settings.BASE_DIR / ".env"
        secrets = _env_secrets(env_path)
        if not secrets:
            self.skipTest(".env yok ya da sir icermiyor (CI'da normal)")

        tracked = subprocess.run(
            ["git", "ls-files"], cwd=settings.BASE_DIR,
            capture_output=True, text=True, check=True).stdout.split("\n")
        tracked = [f for f in tracked if f]

        leaked = {}
        for name, value in secrets.items():
            found = subprocess.run(
                ["git", "grep", "-I", "-l", "-F", value, "--", *tracked],
                cwd=settings.BASE_DIR, capture_output=True, text=True)
            files = sorted({f for f in found.stdout.split("\n") if f})
            if files:
                leaked[name] = files

        self.assertEqual(
            leaked, {},
            "Bu degiskenlerin DEGERI git'e girmis. Depo herkese acik: "
            "dosyadan cikar, sonra anahtari MUTLAKA yenile — gecmisten "
            "silmek yetmez, kopyalanmis olabilir.\n"
            + "\n".join(f"  {n}: {', '.join(f)}" for n, f in leaked.items()))

    def test_env_itself_is_not_tracked(self):
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=settings.BASE_DIR,
            capture_output=True, text=True, check=True).stdout.split("\n")
        bad = [f for f in tracked
               if f == ".env" or f.startswith(".env.") and f != ".env.example"]
        self.assertEqual(bad, [], f".env git'e eklenmis: {bad}")
