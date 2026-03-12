# Generated manually to add brand field to SerializedItem
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_serializeditem_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='serializeditem',
            name='brand',
            field=models.CharField(max_length=100, null=True, blank=True, help_text='Manufacturer/brand (optional)'),
        ),
    ]
