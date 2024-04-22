# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os

from django.db import models
import numpy as np
from simpleeval import simple_eval
import traceback

from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import pytz

from pyscada.models import Unit, Variable

def caluculate_timestamps(start_datetime, end_datetime, interval_length=60*60, include_start=True, include_end=True):
    if type(interval_length) is int or type(interval_length) is float:
        return np.arange(
                start_datetime.timestamp() + (interval_length if not include_start else 0),
                end_datetime.timestamp() + (interval_length if include_end else 0),
                interval_length
            )

    if type(interval_length) is str:
        if interval_length not in ["day", "hour", "month", "quarter", "year"]:
            return []

        if interval_length.lower() == "day":
            return caluculate_timestamps(
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    interval_length=60*60*24,
                    include_start=include_start,
                    include_end=include_end
                )

        if interval_length.lower() == "hour":
            return caluculate_timestamps(
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    interval_length=60*60,
                    include_start=include_start,
                    include_end=include_end
                )

        result = []
        result.append(start_datetime)

        if interval_length.lower() == "month":
            while result[-1] < end_datetime:
                result.append(result[-1] + relativedelta(months=1))

        if interval_length.lower() == "quarter":
            while result[-1] < end_datetime:
                result.append(result[-1] + relativedelta(months=3))

        if interval_length.lower() == "year":
            while result[-1] < end_datetime:
                result.append(result[-1] + relativedelta(years=1))

        if not include_start:
            result = result[1:]

        if not include_end:
            result = result[:-1]

        return np.asarray([item.timestamp() for item in result])

def metering_point_data(meterin_point_id, start_datetime, end_datetime, interval_length):
    mp = MeteringPoint.objects.filter(pk=meterin_point_id).first()
    if mp is None:
        timestamps = caluculate_timestamps(start_datetime=start_datetime, end_datetime=end_datetime, interval_length=interval_length, include_start=False)
        return timestamps, np.zeros(timestamps.shape)

    timestamps, energy = mp.energy_data(start_datetime, end_datetime, interval_length)
    return timestamps, energy


def virtual_metering_point_data(virtual_metering_point_id, start_datetime, end_datetime, interval_length):
    vmp = VirtualMeteringPoint.objects.filter(pk=virtual_metering_point_id).first()
    if vmp is None:
        timestamps = caluculate_timestamps(start_datetime=start_datetime, end_datetime=end_datetime, interval_length=interval_length, include_start=False)
        return timestamps, np.zeros(timestamps.shape)

    return vmp.eval(start_datetime, end_datetime, interval_length)


class CalculationSyntaxError(Exception):
    pass


def eval_calculation(calculation, start_datetime, end_datetime, interval_length=60*60):
    timestamps = caluculate_timestamps(start_datetime=start_datetime, end_datetime=end_datetime, interval_length=interval_length, include_start=False)

    if calculation=="":
        return timestamps, np.zeros(timestamps.shape)

    def mp_data(mp_id):
        return metering_point_data(mp_id, start_datetime, end_datetime, interval_length)[1]


    def vmp_data(vmp_id):
        return virtual_metering_point_data(vmp_id, start_datetime, end_datetime, interval_length)[1]

    try:
        result = simple_eval(calculation, functions={"mp": mp_data, "vmp":vmp_data})
    except:
        return timestamps, np.zeros(timestamps.shape)

    return timestamps, result


class ListElement(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        abstract = True

class EnergyValue(models.DecimalField):
    description = "DecimalField (up to 6 decimal places and 24 digits)"

    def __init__(self, *args, **kwargs):
        kwargs["decimal_places"] = 6
        kwargs["max_digits"] = 18+kwargs["decimal_places"]
        super().__init__(*args, **kwargs)

class Utility(ListElement):
    pass


class BuildingCategory(ListElement):
    pass


class VirtualMeteringPointCategory(ListElement):
    pass

class VirtualMeteringPointGroup(ListElement):
    pass

class AttributeKey(ListElement):
    show_in_meteringpoint_admin = models.BooleanField(default=False)
    show_in_energymeter_admin = models.BooleanField(default=False)
    show_in_calculation_unit_area_admin = models.BooleanField(default=False)

    show_from_mp_in_em_admin = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}({self.pk})"


class FloatAttributeKey(ListElement):
    pass


class Attribute(models.Model):
    key = models.ForeignKey(AttributeKey, on_delete=models.CASCADE, null=True)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.value}"

    class Meta:
        abstract = True
        ordering = ["key"]


class FloatAttribute(models.Model):
    key = models.ForeignKey(FloatAttributeKey, on_delete=models.CASCADE, null=True)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.value}"

    class Meta:
        abstract = True
        ordering = ["key"]


class Address(models.Model):
    street = models.CharField(max_length=255)
    zip = models.CharField(max_length=10)
    town = models.CharField(max_length=255)

    def __str__(self):
        return "%s, %s, %s" % (self.street, self.zip, self.town)

    class Meta:
        ordering = ["street"]


class Building(models.Model):
    number = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=25)
    contruction_date = models.DateField()
    category = models.ForeignKey(BuildingCategory, on_delete=models.CASCADE)
    site = models.CharField(max_length=255)
    address = models.ForeignKey(Address, on_delete=models.CASCADE, null=True)
    comment = models.TextField(blank=True, default="")

    def __str__(self):
        return "%s (%d)" % (self.short_name, self.number)


class BuildingInfo(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, null=True)
    periode_from = models.DateField()
    periode_to = models.DateField()
    cost_unit = models.CharField(max_length=255)
    owner = models.CharField(max_length=255)
    area_net = models.FloatField()
    area_HNF_1_6 = models.FloatField()
    area_NNF_7 = models.FloatField()
    area_FF_8 = models.FloatField()
    area_VF_9 = models.FloatField()
    nb_floors = models.FloatField()
    nb_rooms = models.FloatField()


class CalulationUnitArea(models.Model):
    name = models.CharField(max_length=255, default="", blank=True)
    def __str__(self):
        return f"{self.name}"

    class Meta:
        ordering = ["name"]

class Location(models.Model):

class CalulationUnitAreaAttribute(Attribute):
    calculation_unit_area = models.ForeignKey(CalulationUnitArea, on_delete=models.CASCADE)


class CalulationUnitAreaPeriod(models.Model):
    label = models.CharField(max_length=255, blank=True, null=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    def __str__(self):
        return f"{self.label} {self.valid_from} - {self.valid_to}"


class CalulationUnitAreaPart(FloatAttribute):
    calculation_unit_area_period = models.ForeignKey(
        CalulationUnitAreaPeriod,
        on_delete=models.CASCADE
    )
    calculation_unit_area = models.ForeignKey(
        CalulationUnitArea,
        on_delete=models.CASCADE
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE,
        blank=True,
        null=True
    )
    def __str__(self):
        return f"{self.key}: {self.value} {self.unit.unit if self.unit is not None else '-'}"
    building = models.ForeignKey(Building, on_delete=models.CASCADE, null=True)
    room = models.CharField(max_length=255)
    comment = models.TextField(blank=True, default="")

    def __str__(self):
        return "%s (%s)" % (self.building.short_name, self.room)

class MeteringPointProto(models.Model):
    name = models.CharField(max_length=255, blank=True, default="")
    utility = models.ForeignKey(
        Utility, on_delete=models.CASCADE, null=True, blank=True
    )
    comment = models.CharField(max_length=255, default="", blank=True)
    in_operation_from = models.DateField(null=True, blank=True)
    in_operation_to = models.DateField(null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.SET(1), blank=True, null=True)
    class Meta:
        abstract = True
        ordering = ("name",)


class MeteringPoint(MeteringPointProto):
    location = models.ForeignKey(Location, blank=True, null=True, on_delete=models.SET_NULL) # changeme
    higher_level_metering_points = models.ManyToManyField("MeteringPoint", blank=True)

    def __str__(self):
        return f"{self.name}, {', '.join(list(self.energymeter_set.all().values_list('id_int',flat=True)))} ({self.utility.name if self.utility else '-'})"

    def energy_data(self, start_datetime=None, end_datetime=None, interval_length=60*60*24, use_load_profile=False, timestamps=None):

        if start_datetime is None and end_datetime is None and timestamps is None:
            return [], []

        if timestamps is None:
            timestamps = caluculate_timestamps(
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    interval_length=interval_length,
                    include_start=True,
                    include_end=True,
                )
        else:
            start_datetime = datetime.fromtimestamp(timestamps[0], pytz.timezone("utc"))
            end_datetime = datetime.fromtimestamp(timestamps[-1], pytz.timezone("utc"))

        if start_datetime >= end_datetime:
            return [], []

        data = np.zeros((timestamps.size-1,))

        for meter in self.energymeter_set.all():
            _, energy_data = meter.energy_data(timestamps=timestamps)

            data += energy_data

        if use_load_profile:
            # todo add loadprofile
            pass

        return timestamps[1:], data

    def update_calculated_energy_deltas(self, start_datetime, end_datetime):

        for interval_length in CalulatedMeteringPointEnergyDeltaInterval.objects.all():
            timestamps, data = self.energy_data(start_datetime=start_datetime, end_datetime=end_datetime, interval_length=interval_length.get_interval_length())

            CalulatedMeteringPointEnergyDelta.objects.filter(metering_point=self, interval_length=interval_length).delete()
            new_items = []
            for i in range(len(data)):
                new_items.append(CalulatedMeteringPointEnergyDelta(
                        interval_length=interval_length,
                        energy_delta=data[i],
                        reading_date=datetime.fromtimestamp(timestamps[i]).replace(tzinfo=pytz.timezone("UTC")),
                        metering_point=self
                    ))
            CalulatedMeteringPointEnergyDelta.objects.bulk_create(new_items)


    def get_first_datetime(self, default=None):
        if self.energymeter_set.count() == 0:
            return default

        first_datetime = default
        for meter in self.energymeter_set.all():
            first_datetime_tmp = meter.get_first_datetime(default=datetime.now())

            if type(first_datetime) is datetime:
                if first_datetime_tmp < first_datetime:
                    first_datetime = first_datetime_tmp
            else:
                first_datetime = first_datetime_tmp

        return first_datetime


    def get_last_datetime(self, default=None):
        if self.energymeter_set.count() == 0:
            return default

        last_datetime = default
        for meter in self.energymeter_set.all():
            last_datetime_tmp = meter.get_last_datetime(default=datetime.fromtimestamp(0))

            if type(last_datetime) is datetime:
                if last_datetime_tmp > last_datetime:
                    last_datetime = last_datetime_tmp
            else:
                last_datetime = last_datetime_tmp

        return last_datetime

    def dp_count(self):
        count = 0
        for energy_meter in self.energymeter_set.all():
            count += energy_meter.energyreading_set.count()
        return count


    class Meta:
        ordering = ("name",)


class MeteringPointAttribute(Attribute):
    metering_point = models.ForeignKey(MeteringPoint, on_delete=models.CASCADE)


class VirtualMeteringPoint(MeteringPointProto):
    calculation = models.TextField(default="", blank=True)
    in_operation_from = models.DateField(null=True, blank=True)
    in_operation_to = models.DateField(null=True, blank=True)
    category = models.ForeignKey(
        VirtualMeteringPointCategory, on_delete=models.CASCADE, null=True, blank=True
    )
    group = models.ForeignKey(
        VirtualMeteringPointGroup, on_delete=models.CASCADE, null=True, blank=True
    )

    unit_area = models.ForeignKey(
        CalulationUnitArea,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    def __str__(self):
        return f"{self.name} ({self.utility.name if self.utility else '-'})"


    def eval(self, start_datetime, end_datetime, interval_length=60*60):
        return eval_calculation(calculation=self.calculation, start_datetime=start_datetime, end_datetime=end_datetime, interval_length=interval_length)

    def check_calculation(self):
        if self.calculation == "":
            return None, "calculation is empty string"

        def mp_data(mp_id):
            mp = MeteringPoint.objects.filter(pk=mp_id).first()
            if mp is None:
                raise ValueError(f"{mp_id} not found")
            return 1.0

        def vmp_data(vmp_id):
            vmp = VirtualMeteringPoint.objects.filter(pk=vmp_id).first()
            if vmp is None:
                return f"{vmp_id} not found"
            result, error_text = vmp.check_calculation()
            if result is None:
                raise CalculationSyntaxError(error_text)
            return result

        try:
            result = simple_eval(self.calculation, functions={"mp": mp_data, "vmp":vmp_data})
            return result, ""
        except:
            return None, traceback.format_exc()

    class Meta:
        ordering = ("name",)


class VirtualMeteringPointAttribute(Attribute):
    metering_point = models.ForeignKey(VirtualMeteringPoint, on_delete=models.CASCADE)


class EnergyMeter(models.Model):
    id_ext = models.CharField(max_length=255, blank=True)
    id_int = models.CharField(max_length=255, blank=True)
    comment = models.CharField(max_length=255, default="", blank=True)
    in_operation_from = models.DateField(null=True, blank=True)
    in_operation_to = models.DateField(null=True, blank=True)
    metering_point = models.ForeignKey(
        MeteringPoint, on_delete=models.CASCADE, null=True, blank=True
    )
    factor = models.FloatField(default=1, blank=True)
    initial_value = EnergyValue(default=0, blank=True)
    meter_type_choices = [
        ("upcounting","Up-Counting"),
        ("energydelta","Energy Delta"),
    ]

    meter_type = models.CharField(max_length=255, default="upcounting", choices=meter_type_choices)

    def __str__(self):
        return f"{self.metering_point.name if self.metering_point else '-'}({self.pk}) ({self.id_ext}, {self.id_int})"

    def get_readings(self, start_datetime=None, end_datetime=None, dtype=float, apply_factor=True, convert_to_upcounting=True, datetime_boundary="outside"):

        if start_datetime is None and end_datetime is None:
            energy_readings = self.energyreading_set.all()

        else:
            if start_datetime is None:
                start_datetime = self.energyreading_set.first().reading_date

            if end_datetime is None:
                end_datetime = self.energyreading_set.last().reading_date

            if datetime_boundary == "outside":

                start_datetime_tmp = self.energyreading_set.filter(reading_date__lte=start_datetime).last() # get the datetime that is right outside the window

                if start_datetime_tmp:
                    start_datetime = start_datetime_tmp.reading_date

                end_datetime_tmp = self.energyreading_set.filter(reading_date__gte=end_datetime).first() # get the datetime that is right outside the window

                if end_datetime_tmp:
                    end_datetime = end_datetime_tmp.reading_date

            energy_readings = self.energyreading_set.filter(reading_date__gte=start_datetime, reading_date__lte=end_datetime)

        meter_readings = [dtype(item) for item in energy_readings.values_list('reading',flat=True)]
        meter_timestamps = [item.timestamp() for item in energy_readings.values_list('reading_date',flat=True)]

        #if self.in_operation_from and datetime.fromordinal(self.in_operation_from.toordinal()).timestamp() not in meter_timestamps:
        #    meter_timestamps = [datetime.fromordinal(self.in_operation_from.toordinal()).timestamp()] + meter_timestamps
        #    meter_readings = [dtype(self.initial_value)] + meter_readings

        meter_readings = np.asarray(meter_readings)
        meter_timestamps = np.asarray(meter_timestamps)

        if self.meter_type in ["energydelta"] and convert_to_upcounting:
            meter_readings = np.cumsum(meter_readings)
            if self.in_operation_from is not None:
                initial_date = datetime.fromordinal(self.in_operation_from.toordinal()).timestamp()
                meter_readings = np.insert(meter_readings, 0,0)
                meter_timestamps = np.insert(meter_timestamps, 0, initial_date)

        if apply_factor:
            meter_readings *= self.factor # apply factor

        return meter_timestamps, meter_readings

    def energy_data(self, start_datetime=None, end_datetime=None, interval_length=60*60*24, use_load_profile=False, timestamps=None):

        if start_datetime is None and end_datetime is None and timestamps is None:
            return [], []

        if timestamps is None:
            if start_datetime >= end_datetime:
                return [], []
            timestamps = caluculate_timestamps(
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    interval_length=interval_length,
                    include_start=True,
                    include_end=True,
                )
        else:
            start_datetime = datetime.fromtimestamp(timestamps[0], pytz.timezone("utc"))
            end_datetime = datetime.fromtimestamp(timestamps[-1], pytz.timezone("utc"))



        meter_timestamps, meter_readings = self.get_readings(start_datetime=start_datetime, end_datetime=end_datetime)

        if len(meter_readings) < 2:
            return timestamps[1:], np.zeros((timestamps.size-1,))

        energy_data = np.diff(np.interp(timestamps, meter_timestamps, meter_readings))

        return timestamps[1:], energy_data


    def check_readings(self):
        meter_timestamps, meter_readings = self.get_readings(convert_to_upcounting=True)

    def get_first_datetime(self, default=None):
        energy_reading = self.energyreading_set.first()

        if energy_reading is None:
            return default

        return energy_reading.reading_date

    def get_last_datetime(self, default=None):
        energy_reading = self.energyreading_set.last()

        if energy_reading is None:
            return default

        return energy_reading.reading_date


class EnergyMeterVariableValueType(ListElement):
    pass


class EnergyMeterAttribute(Attribute):
    energy_meter = models.ForeignKey(EnergyMeter, on_delete=models.CASCADE)


class EnergyReading(models.Model):
    reading_date = models.DateTimeField(db_index=True) # timestamp of the reading
    reading = EnergyValue(default=0) # upcountig meterreading
    energy_meter = models.ForeignKey(EnergyMeter, on_delete=models.CASCADE)
    class Meta:
        ordering = ("reading_date",)


class DataEntryForm(models.Model):
    label = models.CharField(max_length=255)
    show_previous_value = models.BooleanField()

    def web_id(self):
        return f"ems_form-{self.id.__str__()}"

    def __str__(self):
        return f"{self.label}({self.id})"


class DataEntryFormElement(models.Model):
    label = models.CharField(max_length=255, blank=True, null=True)
    position = models.SmallIntegerField()
    form = models.ForeignKey(DataEntryForm, on_delete=models.CASCADE)
    data_point = models.ForeignKey(MeteringPoint, on_delete=models.CASCADE)

    def web_id(self):
        return f"ems_form-{self.form.id.__str__()}-{self.id.__str__()}"

    def web_label(self):
        return self.label or self.data_point.label

    def web_unit(self):
        return "fixme"

    def previous_value(self):
        return 1234

    def previous_time(self):
        return "2011-11-11T11:11"

    def __str__(self):
        return f"{self.label}({self.position})"

    class Meta:
        ordering = ["position"]


class AttachmentCategory(ListElement):
    pass


class Attachment(models.Model):
    label = models.CharField(max_length=255)
    attached_file = models.FileField(upload_to="uploads/%Y/%m/")
    datetime_changed = models.DateTimeField(auto_now=True, auto_now_add=False)
    datetime_added = models.DateTimeField(auto_now=False, auto_now_add=True)
    category = models.ForeignKey(
            AttachmentCategory, on_delete=models.SET_NULL,
            blank=True,
            null=True
        )

    def __str__(self):
        return f"{self.label} ({os.path.basename(self.attached_file.name)})"

    class Meta:
        ordering = ["label", "datetime_added"]

class MeteringPointAttachment(models.Model):
    metering_point = models.ForeignKey(
        MeteringPoint, on_delete=models.CASCADE)
    attachment = models.ForeignKey(
        Attachment, on_delete=models.CASCADE
    )


class VirtualMeteringPointAttachment(models.Model):
    virtual_metering_point = models.ForeignKey(
        VirtualMeteringPoint, on_delete=models.CASCADE)
    attachment = models.ForeignKey(
        Attachment, on_delete=models.CASCADE
    )


class EnergyMeterAttachment(models.Model):
    energy_meter = models.ForeignKey(
        EnergyMeter, on_delete=models.CASCADE)
    attachment = models.ForeignKey(
        Attachment, on_delete=models.CASCADE
    )


class CalulatedMeteringPointEnergyDeltaInterval(models.Model):
    interval_length = models.CharField(max_length=20, default="day", help_text="can be hour, day, month, quater, year or number in seconds")

    def get_interval_length(self):
        if self.interval_length.lstrip('-').replace('.','',1).replace('e-','',1).replace('e','',1).isdigit():
            return float(self.interval_length)

        return self.interval_length

    def __str__(self):
        return f"{self.interval_length}"

class CalulatedMeteringPointEnergyDelta(models.Model):
    """
    """
    interval_length = models.ForeignKey(CalulatedMeteringPointEnergyDeltaInterval, on_delete=models.CASCADE)
    energy_delta = EnergyValue()
    reading_date = models.DateTimeField(db_index=True) # timestamp of the reading
    metering_point = models.ForeignKey(MeteringPoint, on_delete=models.CASCADE)

    def energy_data(self, start_datetime, end_datetime, interval_length):
        return self.objects.filter(start_datetime_gte=start_datetime, end_datetime_lte=end_datetime, interval_length=interval_length)
