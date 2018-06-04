# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-06-04 10:09
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('vpn', '0017_auto_20180604_1538'),
    ]

    operations = [
        migrations.CreateModel(
            name='GenerateCertificate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(default='p069d7q7dnz5euhjumdq', max_length=20)),
                ('email_verified', models.CharField(default=False, max_length=5)),
                ('cert_password', models.CharField(blank=True, default='', max_length=20)),
                ('username', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RemoveField(
            model_name='userdetail',
            name='username',
        ),
        migrations.DeleteModel(
            name='UserDetail',
        ),
    ]
