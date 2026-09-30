"""Create the shared cache table the rate limiters depend on.

Done as a migration rather than a documented `manage.py createcachetable`
step so that a deploy cannot silently come up with rate limiting degraded to
per-process counters -- which is exactly the failure that let a card tester
push 9 cards through in 9 minutes on 2026-09-17.
"""
from django.core.management import call_command
from django.db import migrations

TABLE = "vpnsterr_cache"


def create(apps, schema_editor):
    # createcachetable is idempotent: it skips a table that already exists.
    call_command("createcachetable", TABLE,
                 database=schema_editor.connection.alias, verbosity=0)


def drop(apps, schema_editor):
    schema_editor.execute(f'DROP TABLE IF EXISTS "{TABLE}"')


class Migration(migrations.Migration):

    dependencies = [("retention", "0001_initial")]

    operations = [migrations.RunPython(create, drop)]
