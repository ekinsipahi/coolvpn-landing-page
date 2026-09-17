# Record table for Google Play subscription purchases.
#
# Written by hand (produced in an environment where makemigrations could not
# run); the fields must match landing/models.py:PlayPurchase exactly. Verify on
# the server with `python manage.py makemigrations --check`.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('landing', '0006_assistantconversation_assistantmessage_supportticket_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlayPurchase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Replay protection: one token, one account.
                ('purchase_token', models.CharField(db_index=True, max_length=512, unique=True)),
                ('product_id', models.CharField(max_length=64)),
                ('plan_key', models.CharField(max_length=20)),
                ('state', models.CharField(default='other', max_length=16)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('device_uuid', models.CharField(blank=True, default='', max_length=64)),
                ('raw', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='play_purchases', to='landing.subscription')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='play_purchases', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-updated_at',),
            },
        ),
        migrations.AddIndex(
            model_name='playpurchase',
            index=models.Index(fields=['user', 'expires_at'], name='landing_pla_user_id_e6a4d1_idx'),
        ),
    ]
