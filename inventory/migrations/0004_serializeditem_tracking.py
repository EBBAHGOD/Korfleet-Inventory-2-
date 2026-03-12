# Generated migration for adding SerializedItem model and updating InventoryTransaction

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_remove_inventoryitem_brand_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SerializedItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('imei', models.CharField(help_text='Unique IMEI/Serial number', max_length=20, unique=True)),
                ('date_added', models.DateTimeField(default=django.utils.timezone.now)),
                ('price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('condition', models.CharField(choices=[('New', 'New'), ('Used', 'Used'), ('Faulty', 'Faulty')], default='New', max_length=20)),
                ('status', models.CharField(choices=[('Available', 'Available'), ('Issued', 'Issued')], default='Available', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_serialized_items', to=settings.AUTH_USER_MODEL)),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='serialized_items', to='inventory.inventoryitem')),
            ],
            options={
                'verbose_name': 'Serialized Item',
                'verbose_name_plural': 'Serialized Items',
                'ordering': ['-date_added'],
            },
        ),
        migrations.AddField(
            model_name='inventorytransaction',
            name='serialized_item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions', to='inventory.serializeditem'),
        ),
        migrations.AlterField(
            model_name='inventorytransaction',
            name='quantity',
            field=models.IntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)]),
        ),
    ]
