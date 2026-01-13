# Generated manually for FCMDevice model

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('django_communication', '0011_message_read_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='message',
            name='status',
            field=models.CharField(choices=[('queued', 'Queued'), ('sending', 'Sending'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read'), ('failed', 'Failed'), ('bounced', 'Bounced')], default='queued', max_length=20),
        ),
        migrations.CreateModel(
            name='FCMDevice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('registration_id', models.TextField(help_text='FCM registration token (device token)')),
                ('platform', models.CharField(choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')], default='android', help_text='Device platform', max_length=10)),
                ('device_id', models.CharField(blank=True, help_text='Unique device identifier (Android ID, IDFV, etc.)', max_length=255)),
                ('device_name', models.CharField(blank=True, help_text="Friendly device name (e.g., 'Pixel 7 Pro')", max_length=100)),
                ('app_version', models.CharField(blank=True, help_text="App version (e.g., '1.0.0')", max_length=20)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this device is active for notifications')),
                ('last_successful_push', models.DateTimeField(blank=True, help_text='When the last push was successfully sent', null=True)),
                ('failure_count', models.PositiveIntegerField(default=0, help_text='Consecutive push failures (reset on success)')),
                ('user', models.ForeignKey(help_text='User who owns this device', on_delete=django.db.models.deletion.CASCADE, related_name='fcm_devices', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'FCM Device',
                'verbose_name_plural': 'FCM Devices',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='fcmdevice',
            index=models.Index(fields=['user', 'is_active'], name='django_comm_user_id_fcm_idx'),
        ),
        migrations.AddIndex(
            model_name='fcmdevice',
            index=models.Index(fields=['registration_id'], name='django_comm_registr_fcm_idx'),
        ),
        migrations.AddIndex(
            model_name='fcmdevice',
            index=models.Index(fields=['platform', 'is_active'], name='django_comm_platfor_fcm_idx'),
        ),
        migrations.AddConstraint(
            model_name='fcmdevice',
            constraint=models.UniqueConstraint(fields=('user', 'registration_id'), name='unique_user_fcm_token'),
        ),
    ]
