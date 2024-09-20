# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import csv
import io
import os
import re
import traceback
from datetime import datetime

import numpy as np
import pytz
import xlsxwriter
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from scipy.interpolate import interp1d
from simpleeval import simple_eval

from pyscada.models import Unit


def calculate_timestamps(
    start_datetime,
    end_datetime,
    interval_length=60 * 60,
    include_start=True,
    include_end=True,
):
    if type(interval_length) is int or type(interval_length) is float:
        return np.arange(
            start_datetime.timestamp() + (interval_length if not include_start else 0),
            end_datetime.timestamp() + (interval_length if include_end else 0),
            interval_length,
        )

    if type(interval_length) is str:
        if interval_length not in ["day", "hour", "month", "quarter", "year"]:
            return []

        if interval_length.lower() == "day":
            return calculate_timestamps(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval_length=60 * 60 * 24,
                include_start=include_start,
                include_end=include_end,
            )

        if interval_length.lower() == "hour":
            return calculate_timestamps(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval_length=60 * 60,
                include_start=include_start,
                include_end=include_end,
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


def metering_point_data(
    meterin_point_id, start_datetime, end_datetime, interval_length
):
    mp = MeteringPoint.objects.filter(pk=meterin_point_id).first()
    if mp is None:
        timestamps = calculate_timestamps(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            interval_length=interval_length,
            include_start=False,
        )
        return timestamps, np.zeros(timestamps.shape)

    timestamps, energy = mp.energy_data(start_datetime, end_datetime, interval_length)
    return timestamps, energy


def virtual_metering_point_data(
    virtual_metering_point_id, start_datetime, end_datetime, interval_length
):
    vmp = VirtualMeteringPoint.objects.filter(pk=virtual_metering_point_id).first()
    if vmp is None:
        timestamps = calculate_timestamps(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            interval_length=interval_length,
            include_start=False,
        )
        return timestamps, np.zeros(timestamps.shape)

    return vmp.eval(start_datetime, end_datetime, interval_length)


class CalculationSyntaxError(Exception):
    pass


def eval_calculation(
    calculation, start_datetime, end_datetime, interval_length=60 * 60, timestamps=None
):

    if start_datetime is None and end_datetime is None and timestamps is None:
        return [], []

    if timestamps is None:
        timestamps = calculate_timestamps(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            interval_length=interval_length,
            include_start=False,
            include_end=True,
        )
    else:
        start_datetime = datetime.fromtimestamp(timestamps[0], pytz.timezone("utc"))
        end_datetime = datetime.fromtimestamp(timestamps[-1], pytz.timezone("utc"))

        timestamps = calculate_timestamps(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            interval_length=interval_length,
            include_start=False,
            include_end=True,
        )

    if start_datetime >= end_datetime:
        return [], []

    if calculation == "":
        return timestamps, np.zeros(timestamps.shape)

    def mp_data(mp_id):
        return metering_point_data(
            mp_id, start_datetime, end_datetime, interval_length
        )[1]

    def vmp_data(vmp_id):
        return virtual_metering_point_data(
            vmp_id, start_datetime, end_datetime, interval_length
        )[1]

    try:
        result = simple_eval(
            calculation, functions={"mp": mp_data, "vmp": vmp_data}
        ) * np.ones(timestamps.shape)
    except Exception:
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
        kwargs["max_digits"] = 18 + kwargs["decimal_places"]
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


class CalculationUnitArea(models.Model):
    name = models.CharField(max_length=255, default="", blank=True)

    def __str__(self):
        return f"{self.name}"

    """
    def areas(self, timestamps):
        attribute_valid_from = self.calculationunitareaattribute_set.values_list(
                                                        "valid_from",flat=True)
        area_timestamps = [ datetime.fromordinal(item.toordinal()).timestamp() \
                            for item in attribute_valid_from]
        data = {}
        for item in self.calculationunitareaattribute_set():
            energy_price_list = self.energypriceperiod_set.values_list(
                            "price",
                            flat=True)
            area_data = [float(item)for item in energy_price_list]
            data[item.] = interp1d(price_timestamps, price_data, kind='previous',
                                    fill_value="extrapolate")(timestamps)
        return
    """

    class Meta:
        ordering = ["name"]


class CalculationUnitAreaAttribute(Attribute):
    calculation_unit_area = models.ForeignKey(
        CalculationUnitArea, on_delete=models.CASCADE
    )


class CalculationUnitAreaPeriod(models.Model):
    label = models.CharField(max_length=255, blank=True, null=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(
        null=True, blank=True
    )  # will be ignored for now and deleted in the future

    def __str__(self):
        return f"{self.label} {self.valid_from} - {self.valid_to}"


class CalculationUnitAreaPart(FloatAttribute):
    calculation_unit_area_period = models.ForeignKey(
        CalculationUnitAreaPeriod, on_delete=models.CASCADE
    )
    calculation_unit_area = models.ForeignKey(
        CalculationUnitArea, on_delete=models.CASCADE
    )
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        unit = self.unit.unit if self.unit is not None else "-"
        return f"{self.key}: {self.value} {unit}"


class EnergyPrice(models.Model):
    name = models.CharField(max_length=255, default="", blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    per_unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE, related_name="per_unit"
    )
    utility = models.ForeignKey(Utility, on_delete=models.CASCADE)

    # fixme add validation, energy price utility and metering point
    # utility must be equal
    def __str__(self):
        return (
            f"{self.name}: {self.utility.name} in {self.unit.unit}/{self.per_unit.unit}"
        )

    def energy_prices(self, timestamps):
        """ """
        price_timestamps = [
            datetime.fromordinal(item.toordinal()).timestamp()
            for item in self.energypriceperiod_set.values_list("valid_from", flat=True)
        ]
        price_data = [
            float(item)
            for item in self.energypriceperiod_set.values_list("price", flat=True)
        ]
        # fixme handle price changes within a timestamps interval
        return interp1d(
            price_timestamps, price_data, kind="previous", fill_value="extrapolate"
        )(timestamps)


class EnergyPricePeriod(models.Model):
    energy_price = models.ForeignKey(EnergyPrice, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=12, decimal_places=6)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(
        null=True, blank=True
    )  # will be ignored for now and deleted in the future
    # fixme add validation, only one energy_price for all periodes
    # fixme add option to add documents


class WeatherAdjustment(models.Model):
    utility = models.ForeignKey(
        Utility, on_delete=models.CASCADE, null=True, blank=True
    )


class WeatherAdjustmentPeriod(models.Model):
    weather_adjustment = models.ForeignKey(WeatherAdjustment, on_delete=models.CASCADE)
    factor = models.FloatField(default=1.0)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)


class MeteringPointLocation(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, null=True)
    room = models.CharField(max_length=255)
    comment = models.TextField(blank=True, default="")

    def __str__(self):
        return "%s (%s)" % (self.building.short_name, self.room)


class MeteringPointProto(models.Model):
    name = models.CharField(max_length=255, blank=True, default="")
    utility = models.ForeignKey(Utility, on_delete=models.CASCADE)
    comment = models.CharField(max_length=255, default="", blank=True)
    in_operation_from = models.DateField(null=True, blank=True)
    in_operation_to = models.DateField(null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ("name",)


class MeteringPoint(MeteringPointProto):
    location = models.ForeignKey(
        MeteringPointLocation, blank=True, null=True, on_delete=models.SET_NULL
    )  # changeme
    higher_level_metering_points = models.ManyToManyField("MeteringPoint", blank=True)
    energy_price = models.ForeignKey(
        EnergyPrice, on_delete=models.SET_NULL, blank=True, null=True
    )
    load_profile = models.ForeignKey(
        "LoadProfile", on_delete=models.SET_NULL, blank=True, null=True
    )

    def __str__(self):
        id_int_list = ", ".join(
            list(self.energymeter_set.all().values_list("id_int", flat=True))
        )
        utility_name = self.utility.name if self.utility else "-"
        return f"{self.name}, {id_int_list} ({utility_name})"

    def get_energy_price(self):
        if self.energy_price is not None:
            return self.energy_price

        if self.higher_level_metering_points is None:
            return None

        return self.higher_level_metering_points.first().get_energy_price()

    def energy_data(
        self,
        start_datetime=None,
        end_datetime=None,
        interval_length=60 * 60 * 24,
        use_load_profile=False,
        timestamps=None,
    ):

        if start_datetime is None and end_datetime is None and timestamps is None:
            return [], []

        if timestamps is None:
            timestamps = calculate_timestamps(
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

        data = np.zeros((timestamps.size - 1,))

        for meter in self.energymeter_set.all():
            _, energy_data = meter.energy_data(timestamps=timestamps)

            data += energy_data

        if use_load_profile:
            # todo add loadprofile
            pass

        return timestamps[1:], data

    def update_calculated_energy_deltas(self, start_datetime, end_datetime):

        for interval_length in CalculatedMeteringPointEnergyDeltaInterval.objects.all():
            timestamps, data = self.energy_data(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval_length=interval_length.get_interval_length(),
            )

            CalculatedMeteringPointEnergyDelta.objects.filter(
                metering_point=self, interval_length=interval_length
            ).delete()
            new_items = []
            for i in range(len(data)):
                new_items.append(
                    CalculatedMeteringPointEnergyDelta(
                        interval_length=interval_length,
                        energy_delta=data[i],
                        reading_date=datetime.fromtimestamp(timestamps[i]).replace(
                            tzinfo=pytz.utc
                        ),
                        metering_point=self,
                    )
                )
            CalculatedMeteringPointEnergyDelta.objects.bulk_create(new_items)

    def get_first_datetime(self, default=None):
        if self.energymeter_set.count() == 0:
            return default

        first_datetime = default
        for meter in self.energymeter_set.all():
            first_datetime_tmp = meter.get_first_datetime(default=timezone.now())

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
            last_datetime_tmp = meter.get_last_datetime(
                default=datetime(1970, 1, 1, 0, 0, tzinfo=pytz.utc)
            )

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
    calculation = models.TextField(
        default="",
        blank=True,
        help_text=(
            "mp(MeteringPoint.pk) for referencing a MeteringPoint, "
            "vmp(VirtualMeteringPoint.pk) for referencing a VirtualMeteringPoint"
        ),
    )
    in_operation_from = models.DateField(null=True, blank=True)
    in_operation_to = models.DateField(null=True, blank=True)
    category = models.ForeignKey(
        VirtualMeteringPointCategory, on_delete=models.CASCADE, null=True, blank=True
    )

    group = models.ForeignKey(
        VirtualMeteringPointGroup, on_delete=models.CASCADE, null=True, blank=True
    )

    unit_area = models.ForeignKey(
        CalculationUnitArea, on_delete=models.CASCADE, null=True, blank=True
    )

    apply_weather_adjustment = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.utility.name})"

    def eval(self, start_datetime, end_datetime, interval_length=60 * 60):
        return eval_calculation(
            calculation=self.calculation,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            interval_length=interval_length,
        )

    def energy_data(
        self,
        start_datetime=None,
        end_datetime=None,
        interval_length=60 * 60 * 24,
        use_load_profile=False,
        timestamps=None,
    ):

        if start_datetime is None and end_datetime is None and timestamps is None:
            return [], []

        if timestamps is None:
            timestamps = calculate_timestamps(
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

        return eval_calculation(
            calculation=self.calculation,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            interval_length=interval_length,
        )

    def regex_calculation(self, token):
        """finds a regex tocken and add the resulting group matches to a list"""
        matches = []
        for matchNum, match in enumerate(
            re.finditer(token, self.calculation, re.MULTILINE), start=1
        ):
            for groupNum in range(0, len(match.groups())):
                matches.append(match.group(groupNum + 1))
        return matches

    def get_mp_ids_from_calculation(self):
        return self.regex_calculation(token=r"(?<!v)mp\((\d+)\)")

    def get_vmp_ids_from_calculation(self):
        return self.regex_calculation(token=r"vmp\((\d+)\)")

    def check_calculation(self):
        # fixme add dependancy check for vmps

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
            result = simple_eval(
                self.calculation, functions={"mp": mp_data, "vmp": vmp_data}
            )
            return result, ""
        except Exception:
            return None, traceback.format_exc()

    def update_calculated_energy_deltas(self, start_datetime, end_datetime):

        for interval_length in CalculatedMeteringPointEnergyDeltaInterval.objects.all():
            timestamps, data = self.eval(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval_length=interval_length.get_interval_length(),
            )

            CalculatedVirtualMeteringPointEnergyDelta.objects.filter(
                virtual_metering_point=self, interval_length=interval_length
            ).delete()
            new_items = []
            for i in range(len(data)):
                new_items.append(
                    CalculatedVirtualMeteringPointEnergyDelta(
                        interval_length=interval_length,
                        energy_delta=data[i],
                        reading_date=datetime.fromtimestamp(timestamps[i]).replace(
                            tzinfo=pytz.timezone("UTC")
                        ),
                        virtual_metering_point=self,
                    )
                )
            CalculatedVirtualMeteringPointEnergyDelta.objects.bulk_create(new_items)

    def get_first_datetime(self, default=None):

        first_datetime = default

        for vmp_id in self.get_vmp_ids_from_calculation():
            vmp = VirtualMeteringPoint.objects.get(pk=int(vmp_id))
            first_datetime_tmp = vmp.get_first_datetime(default=timezone.now())
            if type(first_datetime) is datetime:
                if first_datetime_tmp < first_datetime:
                    first_datetime = first_datetime_tmp
            else:
                first_datetime = first_datetime_tmp

        for mp_id in self.get_mp_ids_from_calculation():
            mp = MeteringPoint.objects.get(pk=int(mp_id))
            first_datetime_tmp = mp.get_first_datetime(default=timezone.now())
            if type(first_datetime) is datetime:
                if first_datetime_tmp < first_datetime:
                    first_datetime = first_datetime_tmp
            else:
                first_datetime = first_datetime_tmp

        return first_datetime

    def get_last_datetime(self, default=None):

        last_datetime = default

        for vmp_id in self.get_vmp_ids_from_calculation():
            vmp = VirtualMeteringPoint.objects.get(pk=int(vmp_id))
            last_datetime_tmp = vmp.get_last_datetime(
                default=datetime(1970, 1, 1, 0, 0, tzinfo=pytz.utc)
            )
            if type(last_datetime) is datetime:
                if last_datetime_tmp > last_datetime:
                    last_datetime = last_datetime_tmp
            else:
                last_datetime = last_datetime_tmp

        for mp_id in self.get_mp_ids_from_calculation():
            mp = MeteringPoint.objects.get(pk=int(mp_id))
            last_datetime_tmp = mp.get_last_datetime(
                default=datetime(1970, 1, 1, 0, 0, tzinfo=pytz.utc)
            )
            if type(last_datetime) is datetime:
                if last_datetime_tmp > last_datetime:
                    last_datetime = last_datetime_tmp
            else:
                last_datetime = last_datetime_tmp

        return last_datetime

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
        ("upcounting", "Up-Counting"),
        ("energydelta", "Energy Delta"),
    ]

    meter_type = models.CharField(
        max_length=255, default="upcounting", choices=meter_type_choices
    )

    def __str__(self):
        metering_point_name = self.metering_point.name if self.metering_point else "-"
        return f"{metering_point_name}({self.pk}) ({self.id_ext}, {self.id_int})"

    def get_raw_readings(
        self, start_datetime=None, end_datetime=None, datetime_boundary="outside"
    ):

        if start_datetime is None and end_datetime is None:
            return self.energyreading_set.all()

        if start_datetime is None:
            start_datetime = self.energyreading_set.first().reading_date

        if end_datetime is None:
            end_datetime = self.energyreading_set.last().reading_date

        if datetime_boundary == "outside":

            start_datetime_tmp = self.energyreading_set.filter(
                reading_date__lte=start_datetime
            ).last()  # get the datetime that is right outside the window

            if start_datetime_tmp:
                start_datetime = start_datetime_tmp.reading_date

            end_datetime_tmp = self.energyreading_set.filter(
                reading_date__gte=end_datetime
            ).first()  # get the datetime that is right outside the window

            if end_datetime_tmp:
                end_datetime = end_datetime_tmp.reading_date

        return self.energyreading_set.filter(
            reading_date__gte=start_datetime, reading_date__lte=end_datetime
        )

    def get_readings(
        self,
        start_datetime=None,
        end_datetime=None,
        dtype=float,
        apply_factor=True,
        convert_to_upcounting=True,
        datetime_boundary="outside",
    ):

        energy_readings = self.get_raw_readings(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            datetime_boundary=datetime_boundary,
        )

        meter_readings = [
            dtype(item) for item in energy_readings.values_list("reading", flat=True)
        ]
        meter_timestamps = [
            item.timestamp()
            for item in energy_readings.values_list("reading_date", flat=True)
        ]

        meter_readings = np.asarray(meter_readings)
        meter_timestamps = np.asarray(meter_timestamps)

        if self.meter_type in ["energydelta"] and convert_to_upcounting:
            meter_readings = np.cumsum(meter_readings)
            if self.in_operation_from is not None:
                initial_date = datetime.fromordinal(
                    self.in_operation_from.toordinal()
                ).timestamp()
                meter_readings = np.insert(meter_readings, 0, 0)
                meter_timestamps = np.insert(meter_timestamps, 0, initial_date)

        if apply_factor:
            meter_readings *= self.factor  # apply factor

        return meter_timestamps, meter_readings

    def energy_data(
        self,
        start_datetime=None,
        end_datetime=None,
        interval_length=60 * 60 * 24,
        use_load_profile=False,
        timestamps=None,
    ):

        if start_datetime is None and end_datetime is None and timestamps is None:
            return [], []

        if timestamps is None:
            if start_datetime >= end_datetime:
                return [], []

            timestamps = calculate_timestamps(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval_length=interval_length,
                include_start=True,
                include_end=True,
            )
        else:
            start_datetime = datetime.fromtimestamp(timestamps[0], pytz.timezone("utc"))
            end_datetime = datetime.fromtimestamp(timestamps[-1], pytz.timezone("utc"))

        meter_timestamps, meter_readings = self.get_readings(
            start_datetime=start_datetime, end_datetime=end_datetime
        )

        if len(meter_readings) < 2:
            return timestamps[1:], np.zeros((timestamps.size - 1,))

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

    class Meta:
        ordering = ("metering_point__name", "pk")


class EnergyMeterVariableValueType(ListElement):
    pass


class EnergyMeterAttribute(Attribute):
    energy_meter = models.ForeignKey(EnergyMeter, on_delete=models.CASCADE)


class EnergyReadingTariffRegister(ListElement):
    pass


class EnergyReading(models.Model):
    reading_date = models.DateTimeField(db_index=True)  # timestamp of the reading
    reading = EnergyValue(default=0)  # upcountig meterreading
    energy_meter = models.ForeignKey(EnergyMeter, on_delete=models.CASCADE)
    tariff_register = models.ForeignKey(
        EnergyReadingTariffRegister, blank=True, null=True, on_delete=models.CASCADE
    )

    class Meta:
        ordering = ("reading_date",)


class EnergyReadingComment(models.Model):
    energy_reading = models.ForeignKey(EnergyReading, on_delete=models.CASCADE)
    comment = models.CharField(max_length=255, default="", blank=True)


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


class AttachmentGroup(ListElement):
    pass


class Attachment(models.Model):
    label = models.CharField(max_length=255)
    attached_file = models.FileField(upload_to="uploads/%Y/%m/")
    datetime_changed = models.DateTimeField(auto_now=True, auto_now_add=False)
    datetime_added = models.DateTimeField(auto_now=False, auto_now_add=True)
    category = models.ForeignKey(
        AttachmentCategory,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="",
    )

    groups = models.ManyToManyField(AttachmentGroup, blank=True, help_text="")

    def __str__(self):
        return f"{self.label} ({os.path.basename(self.attached_file.name)})"

    class Meta:
        ordering = ["label", "datetime_added"]


class MeteringPointAttachment(models.Model):
    metering_point = models.ForeignKey(MeteringPoint, on_delete=models.CASCADE)
    attachment = models.ForeignKey(Attachment, on_delete=models.CASCADE)


class VirtualMeteringPointAttachment(models.Model):
    virtual_metering_point = models.ForeignKey(
        VirtualMeteringPoint, on_delete=models.CASCADE
    )
    attachment = models.ForeignKey(Attachment, on_delete=models.CASCADE)

    attachment = models.ForeignKey(Attachment, on_delete=models.CASCADE)


class EnergyMeterAttachment(models.Model):
    energy_meter = models.ForeignKey(EnergyMeter, on_delete=models.CASCADE)
    attachment = models.ForeignKey(Attachment, on_delete=models.CASCADE)


class CalculatedMeteringPointEnergyDeltaInterval(models.Model):
    interval_length = models.CharField(
        max_length=20,
        default="day",
        help_text="can be hour, day, month, quater, year or number in seconds",
    )

    def get_interval_length(self):
        if (
            self.interval_length.lstrip("-")
            .replace(".", "", 1)
            .replace("e-", "", 1)
            .replace("e", "", 1)
            .isdigit()
        ):
            return float(self.interval_length)

        return self.interval_length

    def __str__(self):
        return f"{self.interval_length}"


class CalculatedMeteringPointEnergyDeltaProto(models.Model):
    """ """

    interval_length = models.ForeignKey(
        CalculatedMeteringPointEnergyDeltaInterval, on_delete=models.CASCADE
    )
    energy_delta = EnergyValue()
    reading_date = models.DateTimeField(db_index=True)  # timestamp of the reading

    def energy_data(self, start_datetime, end_datetime, interval_length):
        return self.objects.filter(
            start_datetime_gte=start_datetime,
            end_datetime_lte=end_datetime,
            interval_length=interval_length,
        )

    class Meta:
        ordering = ["reading_date"]
        abstract = True


class CalculatedMeteringPointEnergyDelta(CalculatedMeteringPointEnergyDeltaProto):
    metering_point = models.ForeignKey(MeteringPoint, on_delete=models.CASCADE)


class CalculatedVirtualMeteringPointEnergyDelta(
    CalculatedMeteringPointEnergyDeltaProto
):
    virtual_metering_point = models.ForeignKey(
        VirtualMeteringPoint, on_delete=models.CASCADE
    )


class LoadProfileProto(models.Model):
    period_choices = (
        ("year", "Year"),
        ("month", "Month"),
        ("week", "Week"),
        ("day", "Day"),
        ("hour", "Hour"),
        ("none", "None"),
    )
    label = models.CharField(max_length=255)
    period = models.CharField(max_length=10, choices=period_choices, default="week")

    class Meta:
        ordering = ["label"]
        abstract = True


class LoadProfile(LoadProfileProto):
    pass


class LoadProfileValueProto(models.Model):
    date = models.DateTimeField(db_index=True)  # timestamp of the value
    value = models.FloatField()

    class Meta:
        ordering = ("date",)
        abstract = True


class LoadProfileValue(LoadProfileValueProto):
    """ """

    load_profile = models.ForeignKey(LoadProfile, on_delete=models.CASCADE)


class DataExport(models.Model):
    """exports the engery data and meta data"""

    label = models.CharField(max_length=255)

    file_format_choices = (
        ("csv", "CSV"),
        ("xlsx", "Excel xlsx"),
        ("json", "JSON"),
    )
    file_format = models.CharField(max_length=255, choices=file_format_choices)
    periode_from = models.DateTimeField()
    periode_to = models.DateTimeField()
    interval_length = models.ForeignKey(
        CalculatedMeteringPointEnergyDeltaInterval, on_delete=models.CASCADE
    )
    target_timezone_choices = (
        ("UTC", "UTC"),
        ("CET", "CET"),
    )
    target_timezone = models.CharField(max_length=255, choices=target_timezone_choices)

    metering_points = models.ManyToManyField("MeteringPoint", blank=True)
    virtual_metering_points = models.ManyToManyField("VirtualMeteringPoint", blank=True)
    attribute_keys = models.ManyToManyField("AttributeKey", blank=True)
    include_cost = models.BooleanField(help_text="add a column with the energy cost")
    include_coverage = models.BooleanField(
        help_text="add a column with the data coverage of virtual metering points"
    )
    export_file_name = models.CharField(
        max_length=255,
        help_text="name of the Export File without file extension",
        blank=True,
        default="",
    )

    @property
    def periode_from_local(self):
        return self.periode_from.replace(tzinfo=pytz.timezone(settings.TIME_ZONE))

    @property
    def periode_to_local(self):
        return self.periode_to.replace(tzinfo=pytz.timezone(settings.TIME_ZONE))

    @property
    def full_filename(self):
        filename = self.export_file_name
        if filename == "":
            filename = self.label.replace(" ", "_")
            filename += "_"
            filename += self.periode_from.isoformat()
        filename += "." + self.file_format
        return filename

    def prepare_data(self):
        """ """
        interval_length = self.interval_length.interval_length
        datetime_from = self.periode_from
        datetime_to = self.periode_to
        timestamps = calculate_timestamps(
            datetime_from, datetime_to, interval_length=interval_length
        )
        target_timezone_name = self.target_timezone

        # Header
        header = []
        header.append("label")
        header.append("unit")
        header.append("ID")
        attribute_keys = self.attribute_keys.all()

        for key in attribute_keys:
            header.append(key.name)

        header.append("Source Points")

        for timestamp in timestamps[1:]:
            # add one column per timestamp
            dp_date = (
                pytz.timezone(target_timezone_name)
                .fromutc(datetime.fromtimestamp(timestamp))
                .replace(tzinfo=None)
            )
            if self.file_format == "csv":
                header.append(dp_date.isoformat())
            elif self.file_format == "xlsx":
                header.append(dp_date)
            else:
                header.append(dp_date)

        data = []
        for mp in self.metering_points.all():
            data_row = []

            data_row.append(mp.name)  # label/name
            data_row.append(mp.unit.unit if mp.unit is not None else "-")  # unit
            data_row.append(mp.pk)  # ID

            for key in attribute_keys:
                mp_attr = mp.meteringpointattribute_set.filter(key=key).first()
                if mp_attr is None:
                    data_row.append("-")
                else:
                    data_row.append(mp_attr.value)  # todo escape delimiter Char

            data_row.append("-")  # Source Points, tbd
            mp_data = mp.energy_data(
                timestamps=timestamps, interval_length=interval_length
            )[1]
            for value in mp_data:
                data_row.append(value)

            data.append(data_row)

        for mp in self.virtual_metering_points.all():
            data_row = []

            data_row.append(mp.name)  # label/name
            data_row.append(mp.unit.unit if mp.unit is not None else "-")  # unit
            data_row.append(mp.pk)  # ID

            for key in attribute_keys:
                mp_attr = mp.virtualmeteringpointattribute_set.filter(key=key).first()
                if mp_attr is None:
                    data_row.append("-")
                else:
                    data_row.append(mp_attr.value)  # todo escape delimiter Char

            data_row.append("-")  # Source Points, tbd
            mp_data = mp.energy_data(
                timestamps=timestamps, interval_length=interval_length
            )[1]
            for value in mp_data:
                data_row.append(value)

            data.append(data_row)

        return header, data

    def make_file(self, header, data):

        # filename = self.export_file_name

        if self.file_format == "csv":
            pass

        elif self.file_format == "xlsx":
            pass

        else:
            pass

    def make_buffer(self, header, data):
        buffer = io.StringIO()
        if self.file_format == "csv":
            return self.generate_csv(buffer, header, data)

        if self.file_format == "xlsx":

            buffer = io.BytesIO()
            return self.generate_xlsx(buffer, header, data)

        if self.file_format == "json":
            return self.generate_json(buffer, header, data)

        return None

    def generate_csv(self, buffer, header, data):
        """ """

        csv_writer = csv.writer(buffer)

        # write the header
        csv_writer.writerow(header)

        # write the data
        for row in range(len(data)):
            csv_writer.writerow(data[row])

        return buffer

    def generate_xlsx(self, buffer, header, data):
        """ """
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet()
        energy_format = workbook.add_format(
            {"num_format": "#,##0.00", "align": "right"}
        )  # todo get from settings or model
        date_format = workbook.add_format(
            {"num_format": "dd.mmm.yyyy HH:MM", "align": "right"}
        )  # todo get from settings or model

        # write the header
        value_col = None
        for col_num, value in enumerate(header):
            if type(value) is datetime:
                worksheet.write(0, col_num, value, date_format)
                if value_col is None:
                    value_col = col_num
            else:
                worksheet.write(0, col_num, value)

        # write the data
        for row_num, row_values in enumerate(data):
            for col_num, value in enumerate(row_values):
                if col_num >= value_col:
                    worksheet.write(row_num + 1, col_num, value, energy_format)
                else:
                    worksheet.write(row_num + 1, col_num, value)

        workbook.close()
        return buffer

    def generate_json(self, buffer, header, data):
        """ """

        csv_writer = csv.writer(buffer)

        # write the header
        csv_writer.writerow(header)

        # write the data
        for row in range(len(data)):
            csv_writer.writerow(data[row])

        return buffer


"""
class EnergyCost(models.Model):

"""

"""
class Script(models.Model):
    pass
"""

"""
class LoadProfileMin(LoadProfileProto):
    pass

class LoadProfileMinValue(LoadProfileValueProto):
    load_profile = models.ForeignKey(LoadProfileMin, on_delete=models.CASCADE)

class LoadProfileMax(LoadProfileProto):
    pass

class LoadProfileMaxValue(LoadProfileValueProto):
    load_profile = models.ForeignKey(LoadProfileMax, on_delete=models.CASCADE)
"""


"""
calculation token
    energy meter, metering point, virtual metering point, factor, operator, bracket
"""
