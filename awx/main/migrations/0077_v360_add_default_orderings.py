# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-03 14:30
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0076_v360_add_new_instance_group_relations'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='adhoccommand',
            options={'ordering': ('id',)},
        ),
        migrations.AlterModelOptions(
            name='credentialinputsource',
            options={'ordering': ('target_credential', 'source_credential', 'input_field_name')},
        ),
        migrations.AlterModelOptions(
            name='instance',
            options={'ordering': ('hostname',)},
        ),
        migrations.AlterModelOptions(
            name='inventorysource',
            options={'ordering': ('inventory', 'name')},
        ),
        migrations.AlterModelOptions(
            name='inventoryupdate',
            options={'ordering': ('inventory', 'name')},
        ),
        migrations.AlterModelOptions(
            name='notificationtemplate',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='oauth2accesstoken',
            options={'ordering': ('id',), 'verbose_name': 'access token'},
        ),
        migrations.AlterModelOptions(
            name='oauth2application',
            options={'ordering': ('organization', 'name'), 'verbose_name': 'application'},
        ),
        migrations.AlterModelOptions(
            name='role',
            options={'ordering': ('content_type', 'object_id'), 'verbose_name_plural': 'roles'},
        ),
        migrations.AlterModelOptions(
            name='unifiedjob',
            options={'ordering': ('id',)},
        ),
        migrations.AlterModelOptions(
            name='unifiedjobtemplate',
            options={'ordering': ('name',)},
        ),
    ]