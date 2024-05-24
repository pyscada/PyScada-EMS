# Generated by Django 4.2.13 on 2024-05-17 09:20

from django.db import migrations, models
import django.db.models.deletion
import pyscada.ems.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('pyscada', '0109_alter_variable_value_class'),
        ('ems', '0001_add_device_protocol'),
    ]

    operations = [
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('street', models.CharField(max_length=255)),
                ('zip', models.CharField(max_length=10)),
                ('town', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ['street'],
            },
        ),
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=255)),
                ('attached_file', models.FileField(upload_to='uploads/%Y/%m/')),
                ('datetime_changed', models.DateTimeField(auto_now=True)),
                ('datetime_added', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['label', 'datetime_added'],
            },
        ),
        migrations.CreateModel(
            name='AttachmentCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='AttributeKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('show_in_meteringpoint_admin', models.BooleanField(default=False)),
                ('show_in_energymeter_admin', models.BooleanField(default=False)),
                ('show_in_calculation_unit_area_admin', models.BooleanField(default=False)),
                ('show_from_mp_in_em_admin', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Building',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.IntegerField(unique=True)),
                ('name', models.CharField(max_length=255)),
                ('short_name', models.CharField(max_length=25)),
                ('contruction_date', models.DateField()),
                ('site', models.CharField(max_length=255)),
                ('comment', models.TextField(blank=True, default='')),
                ('address', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.address')),
            ],
        ),
        migrations.CreateModel(
            name='BuildingCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CalulatedMeteringPointEnergyDeltaInterval',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('interval_length', models.CharField(default='day', help_text='can be hour, day, month, quater, year or number in seconds', max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name='CalulationUnitArea',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=255)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CalulationUnitAreaPeriod',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(blank=True, max_length=255, null=True)),
                ('valid_from', models.DateField(blank=True, null=True)),
                ('valid_to', models.DateField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='DataEntryForm',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=255)),
                ('show_previous_value', models.BooleanField()),
            ],
        ),
        migrations.CreateModel(
            name='EnergyMeter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_ext', models.CharField(blank=True, max_length=255)),
                ('id_int', models.CharField(blank=True, max_length=255)),
                ('comment', models.CharField(blank=True, default='', max_length=255)),
                ('in_operation_from', models.DateField(blank=True, null=True)),
                ('in_operation_to', models.DateField(blank=True, null=True)),
                ('factor', models.FloatField(blank=True, default=1)),
                ('initial_value', pyscada.ems.models.EnergyValue(blank=True, decimal_places=6, default=0, max_digits=24)),
                ('meter_type', models.CharField(choices=[('upcounting', 'Up-Counting'), ('energydelta', 'Energy Delta')], default='upcounting', max_length=255)),
            ],
            options={
                'ordering': ('metering_point__name', 'pk'),
            },
        ),
        migrations.CreateModel(
            name='EnergyMeterVariableValueType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='EnergyPrice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=255)),
                ('per_unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='per_unit', to='pyscada.unit')),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='pyscada.unit')),
            ],
        ),
        migrations.CreateModel(
            name='FloatAttributeKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='LoadProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=255)),
                ('period', models.CharField(choices=[('year', 'Year'), ('month', 'Month'), ('week', 'Week'), ('day', 'Day'), ('hour', 'Hour'), ('none', 'None')], default='week', max_length=10)),
            ],
            options={
                'ordering': ['label'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MeteringPoint',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=255)),
                ('comment', models.CharField(blank=True, default='', max_length=255)),
                ('in_operation_from', models.DateField(blank=True, null=True)),
                ('in_operation_to', models.DateField(blank=True, null=True)),
                ('energy_price', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ems.energyprice')),
                ('higher_level_metering_points', models.ManyToManyField(blank=True, to='ems.meteringpoint')),
                ('load_profile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ems.loadprofile')),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Utility',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='VirtualMeteringPoint',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=255)),
                ('comment', models.CharField(blank=True, default='', max_length=255)),
                ('calculation', models.TextField(blank=True, default='', help_text='mp(MeteringPoint.pk) for referencing a MeteringPoint, vmp(VirtualMeteringPoint.pk) for referencing a VirtualMeteringPoint')),
                ('in_operation_from', models.DateField(blank=True, null=True)),
                ('in_operation_to', models.DateField(blank=True, null=True)),
                ('apply_weather_adjustment', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='VirtualMeteringPointCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='VirtualMeteringPointGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='WeatherAdjustment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('utility', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.utility')),
            ],
        ),
        migrations.CreateModel(
            name='WeatherAdjustmentPeriod',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('factor', models.FloatField(default=1.0)),
                ('valid_from', models.DateField(blank=True, null=True)),
                ('valid_to', models.DateField(blank=True, null=True)),
                ('weather_adjustment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.weatheradjustment')),
            ],
        ),
        migrations.CreateModel(
            name='VirtualMeteringPointAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=255)),
                ('key', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.attributekey')),
                ('metering_point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.virtualmeteringpoint')),
            ],
            options={
                'ordering': ['key'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='VirtualMeteringPointAttachment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attachment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.attachment')),
                ('virtual_metering_point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.virtualmeteringpoint')),
            ],
        ),
        migrations.AddField(
            model_name='virtualmeteringpoint',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.virtualmeteringpointcategory'),
        ),
        migrations.AddField(
            model_name='virtualmeteringpoint',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.virtualmeteringpointgroup'),
        ),
        migrations.AddField(
            model_name='virtualmeteringpoint',
            name='unit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='pyscada.unit'),
        ),
        migrations.AddField(
            model_name='virtualmeteringpoint',
            name='unit_area',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.calulationunitarea'),
        ),
        migrations.AddField(
            model_name='virtualmeteringpoint',
            name='utility',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.utility'),
        ),
        migrations.CreateModel(
            name='MeteringPointLocation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('room', models.CharField(max_length=255)),
                ('comment', models.TextField(blank=True, default='')),
                ('building', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.building')),
            ],
        ),
        migrations.CreateModel(
            name='MeteringPointAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=255)),
                ('key', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.attributekey')),
                ('metering_point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.meteringpoint')),
            ],
            options={
                'ordering': ['key'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MeteringPointAttachment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attachment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.attachment')),
                ('metering_point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.meteringpoint')),
            ],
        ),
        migrations.AddField(
            model_name='meteringpoint',
            name='location',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ems.meteringpointlocation'),
        ),
        migrations.AddField(
            model_name='meteringpoint',
            name='unit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='pyscada.unit'),
        ),
        migrations.AddField(
            model_name='meteringpoint',
            name='utility',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.utility'),
        ),
        migrations.CreateModel(
            name='LoadProfileValue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(db_index=True)),
                ('value', models.FloatField()),
                ('load_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.loadprofile')),
            ],
            options={
                'ordering': ('date',),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='EnergyReading',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reading_date', models.DateTimeField(db_index=True)),
                ('reading', pyscada.ems.models.EnergyValue(decimal_places=6, default=0, max_digits=24)),
                ('energy_meter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.energymeter')),
            ],
            options={
                'ordering': ('reading_date',),
            },
        ),
        migrations.CreateModel(
            name='EnergyPricePeriod',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('price', models.DecimalField(decimal_places=6, max_digits=12)),
                ('valid_from', models.DateField(blank=True, null=True)),
                ('valid_to', models.DateField(blank=True, null=True)),
                ('energy_price', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.energyprice')),
            ],
        ),
        migrations.AddField(
            model_name='energyprice',
            name='utility',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.utility'),
        ),
        migrations.CreateModel(
            name='EnergyMeterAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=255)),
                ('energy_meter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.energymeter')),
                ('key', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.attributekey')),
            ],
            options={
                'ordering': ['key'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='EnergyMeterAttachment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attachment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.attachment')),
                ('energy_meter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.energymeter')),
            ],
        ),
        migrations.AddField(
            model_name='energymeter',
            name='metering_point',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.meteringpoint'),
        ),
        migrations.CreateModel(
            name='DataEntryFormElement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(blank=True, max_length=255, null=True)),
                ('position', models.SmallIntegerField()),
                ('data_point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.meteringpoint')),
                ('form', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.dataentryform')),
            ],
            options={
                'ordering': ['position'],
            },
        ),
        migrations.CreateModel(
            name='CalulationUnitAreaPart',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=255)),
                ('calculation_unit_area', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.calulationunitarea')),
                ('calculation_unit_area_period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.calulationunitareaperiod')),
                ('key', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.floatattributekey')),
                ('unit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='pyscada.unit')),
            ],
            options={
                'ordering': ['key'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CalulationUnitAreaAttribute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=255)),
                ('calculation_unit_area', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.calulationunitarea')),
                ('key', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.attributekey')),
            ],
            options={
                'ordering': ['key'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CalulatedVirtualMeteringPointEnergyDelta',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('energy_delta', pyscada.ems.models.EnergyValue(decimal_places=6, max_digits=24)),
                ('reading_date', models.DateTimeField(db_index=True)),
                ('interval_length', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.calulatedmeteringpointenergydeltainterval')),
                ('virtual_metering_point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.virtualmeteringpoint')),
            ],
            options={
                'ordering': ['reading_date'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CalulatedMeteringPointEnergyDelta',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('energy_delta', pyscada.ems.models.EnergyValue(decimal_places=6, max_digits=24)),
                ('reading_date', models.DateTimeField(db_index=True)),
                ('interval_length', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.calulatedmeteringpointenergydeltainterval')),
                ('metering_point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.meteringpoint')),
            ],
            options={
                'ordering': ['reading_date'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='BuildingInfo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('periode_from', models.DateField()),
                ('periode_to', models.DateField()),
                ('cost_unit', models.CharField(max_length=255)),
                ('owner', models.CharField(max_length=255)),
                ('area_net', models.FloatField()),
                ('area_HNF_1_6', models.FloatField()),
                ('area_NNF_7', models.FloatField()),
                ('area_FF_8', models.FloatField()),
                ('area_VF_9', models.FloatField()),
                ('nb_floors', models.FloatField()),
                ('nb_rooms', models.FloatField()),
                ('building', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='ems.building')),
            ],
        ),
        migrations.AddField(
            model_name='building',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ems.buildingcategory'),
        ),
        migrations.AddField(
            model_name='attachment',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ems.attachmentcategory'),
        ),
    ]
