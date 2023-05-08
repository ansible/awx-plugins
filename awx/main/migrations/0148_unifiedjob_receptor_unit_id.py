# Generated by Django 2.2.16 on 2021-06-11 04:50

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0147_validate_ee_image_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='unifiedjob',
            name='work_unit_id',
            field=models.CharField(
                blank=True, default=None, editable=False, help_text='The Receptor work unit ID associated with this job.', max_length=255, null=True
            ),
        ),
    ]