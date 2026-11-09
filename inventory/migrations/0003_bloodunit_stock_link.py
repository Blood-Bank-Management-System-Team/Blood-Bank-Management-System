import django.db.models.deletion
from django.db import migrations, models


def link_existing_units(apps, schema_editor):
    """Give every existing BloodUnit an allocatable BloodStock row."""
    BloodUnit = apps.get_model("inventory", "BloodUnit")
    BloodStock = apps.get_model("inventory", "BloodStock")
    for unit in BloodUnit.objects.filter(stock__isnull=True).iterator():
        unit.stock = BloodStock.objects.create(
            blood_group=unit.blood_group,
            location=unit.bank_location,
            available_units=unit.quantity,
            collection_date=unit.collection_date,
            expiry_date=unit.expiry_date,
            status="AVAILABLE" if unit.quantity > 0 else "RESERVED",
        )
        unit.save(update_fields=["stock"])


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_bloodunit_created_by_bloodunit_updated_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="bloodunit",
            name="stock",
            field=models.OneToOneField(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="unit",
                to="inventory.bloodstock",
            ),
        ),
        migrations.AlterField(
            model_name="bloodstock",
            name="location",
            field=models.CharField(max_length=200),
        ),
        migrations.RunPython(link_existing_units, migrations.RunPython.noop),
    ]
