# Site kaydını vpnsterr.com'a sabitler (sitemap/hreflang URL'leri buradan üretilir)
from django.db import migrations


def set_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        id=1, defaults={"domain": "vpnsterr.com", "name": "VPNsterr"}
    )


def unset_site(apps, schema_editor):
    pass  # geri almaya gerek yok


class Migration(migrations.Migration):

    dependencies = [
        ("landing", "0002_device"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(set_site, unset_site),
    ]
