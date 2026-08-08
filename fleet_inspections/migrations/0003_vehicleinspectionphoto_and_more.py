# Generated manually for fleet_inspections general photos and notes update

import django.db.models.deletion
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('fleet_inspections', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vehicleinspection',
            name='notes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='inspectioncheckphoto',
            name='caption',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.CreateModel(
            name='VehicleInspectionPhoto',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('photo', models.ImageField(upload_to='fleet_inspections/general_photos/')),
                ('caption', models.CharField(blank=True, max_length=200, null=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('inspection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='general_photos', to='fleet_inspections.vehicleinspection')),
            ],
            options={
                'ordering': ['uploaded_at'],
            },
        ),
    ]
