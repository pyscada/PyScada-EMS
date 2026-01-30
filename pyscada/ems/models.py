# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import csv
import io
import json
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
from scipy.interpolate import interp1d
from simpleeval import simple_eval

from pyscada.models import Unit, Variable

tz_local = pytz.timezone(settings.TIME_ZONE)


def factor_from_unit(unit):
    if unit == "kWh":
        return 1.0

    if unit == "MWh":
        return 1000.0

    if unit == "Wh":
        return 1.0 / 1000.0
    return 0.0


def make_local_native(datetime_value, target_timezone_name):
    tz_target = pytz.timezone(target_timezone_name)
    datetime_value_local = tz_target.localize(
        datetime.utcfromtimestamp(datetime_value.timestamp())
    )
    return datetime_value_local.replace(tzinfo=None) + datetime_value_local.utcoffset()


def calculate_timestamps(
    start_datetime,
    end_datetime,
    interval=None,
):
    if interval is None:
        interval = CalculatedMeteringPointEnergyDeltaInterval(
            interval_length=str(60 * 60 * 24), timezone=settings.TIME_ZONE
        )

    interval_length = interval.get_interval_length()

    if type(interval_length) is int or type(interval_length) is float:
        return np.arange(
            start_datetime.timestamp(),
            end_datetime.timestamp() + interval_length,
            interval_length,
        )

    if type(interval_length) is str:
        result = []
        if interval_length not in ["day", "week", "month", "quarter", "year"]:
            return result

        start_datetime_local = make_local_native(start_datetime, interval.timezone)
        end_datetime_local = make_local_native(end_datetime, interval.timezone)

        result.append(start_datetime_local)

        if interval_length.lower() == "day":
            day_nb = 1
            while result[-1] < end_datetime_local:
                result.append(start_datetime_local + relativedelta(days=day_nb))
                day_nb += 1

        if interval_length.lower() == "week":
            day_nb = 7
            while result[-1] < end_datetime_local:
                result.append(start_datetime_local + relativedelta(days=day_nb))
                day_nb += 7

        if interval_length.lower() == "month":
            month_nb = 1
            while result[-1] < end_datetime_local:
                result.append(start_datetime_local + relativedelta(months=month_nb))
                month_nb += 1
                # result.append(result[-1] + relativedelta(months=1))

        if interval_length.lower() == "quarter":
            month_nb = 3
            while result[-1] < end_datetime_local:
                result.append(start_datetime_local + relativedelta(months=month_nb))
                month_nb += 3
                # result.append(result[-1] + relativedelta(months=3))

        if interval_length.lower() == "year":
            year_nb = 1
            while result[-1] < end_datetime_local:
                result.append(start_datetime_local + relativedelta(years=year_nb))
                year_nb += 1
                # result.append(result[-1] + relativedelta(years=1))

        return np.asarray([item.timestamp() for item in result])


def virtual_metering_point_data(
    virtual_metering_point_id,
    timestamps,
    interval=None,
    use_precalculated_values=False,
):
    vmp = VirtualMeteringPoint.objects.filter(pk=virtual_metering_point_id).first()
    if vmp is None:
        return timestamps, np.zeros((len(timestamps) - 1))

    return vmp.eval(
        timestamps=timestamps,
        use_precalculated_values=use_precalculated_values,
    )


def calculate_start_datetime(first_datetime, interval):

    start_year = first_datetime.year
    start_month = 1  # first_datetime.month
    start_day = 1  # first_datetime.day
    start_hour = 0
    start_minute = 0
    """
    if interval.interval_length == "year" or interval.interval_length == "quater":
        start_month = 1
        start_day = 1

    elif interval.interval_length == "month":
        start_day = 1
    """
    # if interval.interval_length == "week" or interval.interval_length == "day"
    # is the same as default values

    start_datetime = datetime(
        start_year,
        start_month,
        start_day,
        start_hour,
        start_minute,
        tzinfo=pytz.timezone(interval.timezone),
    )

    if interval.interval_length == "week":
        # special case start of the week shift to the previous monday as start
        # of the week
        # fixme this should reflect the start of the week that is
        # supplied by the user (Sunday or Monday)
        start_datetime = start_datetime - relativedelta(days=first_datetime.weekday())

    return start_datetime


def parse_and_filter_category(category, mps):
    if "&" in category and "|" in category:
        raise CalculationSyntaxError("& and | can't be combined")
    elif "&" in category:
        # AND
        for token in category.split("&"):
            mps = mps.filter(categories__name=token)
    elif "|" in category:
        # OR
        mps = mps.filter(categories__name__in=[token for token in category.split("|")])
    else:
        # just one category
        mps = mps.filter(categories__name=category)

    return mps


class CalculationSyntaxError(Exception):
    pass


class ListElement(models.Model):
    name = models.CharField(max_length=255, unique=True)

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


class MeteringPointCategory(ListElement):
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
    value = models.FloatField()

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
    unit_area = models.ForeignKey(
        "CalculationUnitArea", on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return "%s (%d)" % (self.short_name, self.number)

    class Meta:
        ordering = ["short_name"]


class BuildingInfo(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, null=True)
    periode_from = models.DateField()
    periode_to = models.DateField()
    cost_unit = models.CharField(max_length=255)
    owner = models.CharField(max_length=255)


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

    def add_calculation_unit_area(self, cua):
        """merge the infos from another item into this and sum the areas"""
        # FIXME handle CalculationUnitAreaAttribute
        for external_item in cua.calculationunitareapart_set.all():
            internal_item = self.calculationunitareapart_set.filter(
                key__id=external_item.key.id,
                calculation_unit_area_period__id=external_item.calculation_unit_area_period.id,  # noqa: E501
            ).first()
            if internal_item is None:
                # entry is missing
                internal_item = CalculationUnitAreaPart(
                    key=external_item.key,
                    value=external_item.value,
                    calculation_unit_area_period=external_item.calculation_unit_area_period,  # noqa: E501
                    calculation_unit_area=self,
                    unit=external_item.unit,
                )

            else:
                internal_item.value = float(external_item.value) + float(
                    internal_item.value
                )

            internal_item.save()

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

    class Meta:
        ordering = ["building__short_name", "room"]


class MeteringPointProto(models.Model):
    name = models.CharField(max_length=255, blank=True, default="")
    utility = models.ForeignKey(Utility, on_delete=models.CASCADE)
    comment = models.CharField(max_length=255, default="", blank=True)
    _in_operation_from = models.DateField(null=True, blank=True)
    _in_operation_to = models.DateField(null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, blank=True, null=True)
    last_precalculation_update = models.DateTimeField(null=True, blank=True)
    categories = models.ManyToManyField(MeteringPointCategory, blank=True)

    def reset_related_last_precalculation_update_status(self):
        for vmp in self.get_related_virtual_metering_points():
            vmp.last_precalculation_update = None
            vmp.save()

    def save(self, **kwargs):
        super().save(**kwargs)  # Call the "real" save() method
        if self.last_precalculation_update is None:
            self.reset_related_last_precalculation_update_status()

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

    @property
    def in_operation_from(self):
        if self._in_operation_from is not None:
            return self._in_operation_from

        in_operation_from = None
        for energy_meter in self.energymeter_set.all():
            if (
                in_operation_from is None
                and energy_meter._in_operation_from is not None
            ):
                in_operation_from = energy_meter._in_operation_from

            elif energy_meter._in_operation_from is not None:
                in_operation_from = min(
                    in_operation_from, energy_meter._in_operation_from
                )

        return in_operation_from

    @property
    def in_operation_to(self):
        if self._in_operation_to is not None:
            return self._in_operation_to

        in_operation_to = None
        in_operation_to_is_none = False
        for energy_meter in self.energymeter_set.all():
            if in_operation_to is None and energy_meter._in_operation_to is not None:
                in_operation_to = energy_meter._in_operation_to

            elif energy_meter._in_operation_to is not None:
                in_operation_to = max(in_operation_to, energy_meter._in_operation_to)
            else:
                in_operation_to_is_none = True

        if in_operation_to_is_none:
            in_operation_to = None

        return in_operation_to

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
        interval=None,
        use_load_profile=False,
        timestamps=None,
        use_precalculated_values=True,
    ):

        if (
            start_datetime is None
            and end_datetime is None
            and (timestamps is None or len(timestamps) == 0)
        ):
            return [], []

        if interval is None:
            interval = CalculatedMeteringPointEnergyDeltaInterval(
                interval_length=str(60 * 60 * 24), timezone=settings.TIME_ZONE
            )

        if timestamps is None:
            timestamps = calculate_timestamps(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval=interval,
            )
        else:
            start_datetime = pytz.utc.localize(datetime.utcfromtimestamp(timestamps[0]))
            end_datetime = pytz.utc.localize(datetime.utcfromtimestamp(timestamps[-1]))

        if start_datetime >= end_datetime or len(timestamps) == 0:
            return [], []

        data = np.zeros((len(timestamps) - 1,))

        if (
            use_precalculated_values
            and interval
            in list(CalculatedMeteringPointEnergyDeltaInterval.objects.all())
            and self.last_precalculation_update is not None
        ):
            calculated_deltas = CalculatedMeteringPointEnergyDelta.objects.filter(
                metering_point=self,
                reading_date__gte=start_datetime,
                reading_date__lte=end_datetime,
                interval=interval,
            )
            delta_timestamps = np.asarray(
                [
                    item.timestamp()
                    for item in calculated_deltas.values_list("reading_date", flat=True)
                ]
            )
            delta_energy = np.asarray(
                [
                    float(item)
                    for item in calculated_deltas.values_list("energy_delta", flat=True)
                ]
            )

            for i in range(1, len(timestamps)):
                if timestamps[i] in delta_timestamps:
                    data[i - 1] = delta_energy[
                        np.where(timestamps[i] == delta_timestamps)
                    ]

            return timestamps, data
        print("calculate all values")
        for meter in self.energymeter_set.all():
            _, energy_data = meter.energy_data(timestamps=timestamps)

            if energy_data is None:
                continue

            data += energy_data

        if use_load_profile:
            # todo add loadprofile
            pass

        return timestamps, data

    def update_calculated_energy_deltas(
        self, start_datetime=None, end_datetime=None, intervals=None
    ):
        if intervals is None:
            intervals = CalculatedMeteringPointEnergyDeltaInterval.objects.all()

        start_datetime_in = start_datetime

        for interval in intervals:
            datetime_now = pytz.timezone(interval.timezone).localize(datetime.now())
            first_datetime = self.get_first_datetime(default=datetime_now)

            if start_datetime_in is None:
                start_datetime = calculate_start_datetime(first_datetime, interval)

            if end_datetime is None:
                end_datetime = self.get_last_datetime(default=datetime_now)
            use_precalculated_values = (
                False  # if self.last_precalculation_update is None else True
            )
            timestamps, data = self.energy_data(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval=interval,
                use_precalculated_values=use_precalculated_values,
            )

            # delete all old data
            CalculatedMeteringPointEnergyDelta.objects.filter(
                metering_point=self, interval=interval
            ).delete()

            new_items = []
            for i in range(len(data)):
                if np.isnan(data[i]) or np.isinf(data[i]):
                    continue
                new_items.append(
                    CalculatedMeteringPointEnergyDelta(
                        interval=interval,
                        energy_delta=data[i],
                        reading_date=datetime.utcfromtimestamp(
                            timestamps[i + 1]
                        ).replace(
                            tzinfo=pytz.utc
                        ),  # fix timespamps idx, done
                        metering_point=self,
                    )
                )
            CalculatedMeteringPointEnergyDelta.objects.bulk_create(new_items)
        self.last_precalculation_update = tz_local.localize(datetime.now())
        self.save()

    def get_first_datetime(self, default=None):
        if self.energymeter_set.count() == 0:
            return default

        first_datetime = default
        if self.in_operation_from is not None:
            # if in_operation_from is set limit the first_datetime to that date
            first_datetime = self.in_operation_from

        for meter in self.energymeter_set.all():
            first_datetime_tmp = meter.get_first_datetime(
                default=tz_local.localize(datetime.now())
            )

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

        if self.in_operation_to is not None:
            # if in_operation_to is set limit the last_datetime to that date
            last_datetime = self.in_operation_to

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

    def import_data_from_data_source(self, dry_run=False):
        for energy_meter in self.energymeter_set.all():
            energy_meter.import_data_from_data_source(dry_run=dry_run)

    def get_related_virtual_metering_points(self):
        vmps = []
        for vmp in VirtualMeteringPoint.objects.all():
            if self.pk in vmp.get_mp_ids_from_calculation():
                vmps.append(vmp)

        return vmps

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
            "vmp(VirtualMeteringPoint.pk) for referencing a VirtualMeteringPoint,"
            'dt("unit") for the time difference in either "s": seconds, \
             "h": hours, "d": days'
            'mpcategory("category") for all MetergingPoints that are in the category',
            'vmpcategory("category") for all VirtualMetergingPoints that are \
            in the category',
            "the category can be filter further by combining with & or | but & and | \
            can`t be mixed",
            'e.G. "Cat_A&Cat_B" will only return entries that have Cat_A and Cat_A',
        ),
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

    @property
    def in_operation_from(self):
        return self._in_operation_from

    @property
    def in_operation_to(self):
        return self._in_operation_to

    def eval(
        self,
        start_datetime=None,
        end_datetime=None,
        interval=None,
        timestamps=None,
        use_precalculated_values=None,
    ):

        if start_datetime is None and end_datetime is None and timestamps is None:
            return [], []

        if timestamps is None:
            timestamps = calculate_timestamps(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval=interval,
            )
        else:
            start_datetime = pytz.utc.localize(datetime.utcfromtimestamp(timestamps[0]))
            end_datetime = pytz.utc.localize(datetime.utcfromtimestamp(timestamps[-1]))

        if start_datetime >= end_datetime or len(timestamps) == 0:
            return [], []

        if self.calculation == "":
            return timestamps, np.zeros((len(timestamps) - 1))

        def mp_data(mp_id):
            mp = MeteringPoint.objects.filter(pk=mp_id).first()
            if mp is None:
                return np.zeros((len(timestamps) - 1))

            return mp.energy_data(
                timestamps=timestamps,
                interval=interval,
                use_precalculated_values=(
                    True
                    if use_precalculated_values is None
                    else use_precalculated_values
                ),
            )[1]

        def vmp_data(vmp_id):
            vmp = VirtualMeteringPoint.objects.filter(pk=vmp_id).first()
            if vmp is None:
                return np.zeros((len(timestamps) - 1))

            return vmp.eval(
                timestamps=timestamps,
                interval=interval,
                use_precalculated_values=(
                    True
                    if use_precalculated_values is None
                    else use_precalculated_values
                ),
            )[1]

        def timedelta_data(unit="h"):
            """returns the timedelta between two measurements in the requested unit
            this is e.g. usefull to calculate the average power for a energy meter
            """
            if unit == "h":  # return difference in hours
                return np.diff(timestamps) / 3600.0  # difference in seconds -> hour
            if unit == "s":  # return difference in hours
                return np.diff(timestamps)  # difference in seconds -> seconds
            if unit == "d":  # return difference in hours
                return np.diff(timestamps) / 3600 / 24  # difference in seconds -> days

        def mp_category_data(category):
            """returns the sum of all data in that category"""
            data = np.zeros((len(timestamps) - 1))

            for mp in parse_and_filter_category(
                category, MeteringPoint.objects.filter(utility=self.utility)
            ):
                data += mp.energy_data(
                    timestamps=timestamps,
                    use_precalculated_values=(
                        True
                        if use_precalculated_values is None
                        else use_precalculated_values
                    ),
                )[1]

            return data

        def vmp_category_data(category):
            """returns the sum of all data in that category"""
            data = np.zeros((len(timestamps) - 1))
            for vmp in parse_and_filter_category(
                category, VirtualMeteringPoint.objects.filter(utility=self.utility)
            ):
                data += vmp.eval(
                    timestamps=timestamps,
                    use_precalculated_values=(
                        True
                        if use_precalculated_values is None
                        else use_precalculated_values
                    ),
                )[1]

            return data

        try:
            result = simple_eval(
                self.calculation,
                functions={
                    "mp": mp_data,
                    "vmp": vmp_data,
                    "dt": timedelta_data,
                    "mpcategory": mp_category_data,
                    "vmpcategory": vmp_category_data,
                },
            ) * np.ones((len(timestamps) - 1))

        except Exception:
            print(traceback.format_exc())
            return timestamps, np.zeros((len(timestamps) - 1))

        return timestamps, result

    def energy_data(
        self,
        start_datetime=None,
        end_datetime=None,
        interval=None,
        use_load_profile=False,
        timestamps=None,
        use_precalculated_values=True,
    ):

        if (
            start_datetime is None
            and end_datetime is None
            and (timestamps is None or len(timestamps) == 0)
        ):
            return [], []

        if interval is None:
            interval = CalculatedMeteringPointEnergyDeltaInterval(
                interval_length=str(60 * 60 * 24), timezone=settings.TIME_ZONE
            )

        if timestamps is None:
            timestamps = calculate_timestamps(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval=interval,
            )
        else:
            start_datetime = pytz.utc.localize(datetime.utcfromtimestamp(timestamps[0]))
            end_datetime = pytz.utc.localize(datetime.utcfromtimestamp(timestamps[-1]))

        if start_datetime >= end_datetime:
            return [], []

        if (
            use_precalculated_values
            and interval
            in list(CalculatedMeteringPointEnergyDeltaInterval.objects.all())
            and self.last_precalculation_update is not None
        ):  # fixme check if values for the requested period are precalculated
            calculated_deltas = (
                CalculatedVirtualMeteringPointEnergyDelta.objects.filter(
                    virtual_metering_point=self,
                    reading_date__gte=start_datetime,
                    reading_date__lte=end_datetime,
                    interval=interval,
                )
            )

            delta_timestamps = np.asarray(
                [
                    item.timestamp()
                    for item in calculated_deltas.values_list("reading_date", flat=True)
                ]
            )
            delta_energy = np.asarray(
                [
                    float(item)
                    for item in calculated_deltas.values_list("energy_delta", flat=True)
                ]
            )
            data = np.zeros((len(timestamps) - 1,))

            for i in range(1, len(timestamps)):
                if timestamps[i] in delta_timestamps:
                    data[i - 1] = delta_energy[
                        np.where(timestamps[i] == delta_timestamps)
                    ]
                else:
                    # fixme calculate missing values
                    pass

            return timestamps, data

        return self.eval(
            timestamps=timestamps,
            interval=interval,
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
        ids = [int(id) for id in self.regex_calculation(token=r"(?<!v)mp\((\d+)\)")]
        for category in self.regex_calculation(token=r"(?<!v)mpcategory\(\"(.+)\"\)"):
            ids += list(
                parse_and_filter_category(
                    category, MeteringPoint.objects.filter(utility=self.utility)
                ).values_list("pk", flat=True)
            )

        return ids

    def get_vmp_ids_from_calculation(self):
        ids = [int(id) for id in self.regex_calculation(token=r"vmp\((\d+)\)")]
        for category in self.regex_calculation(token=r"(?<!v)vmpcategory\(\"(.+)\"\)"):
            ids += list(
                parse_and_filter_category(
                    category, VirtualMeteringPoint.objects.filter(utility=self.utility)
                ).values_list("pk", flat=True)
            )

        return ids

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

        def timedelta_data(unit="h"):
            if unit not in ["h", "s", "d"]:
                raise ValueError(f"unit {unit} not found")
            return 1.0

        try:
            result = simple_eval(
                self.calculation,
                functions={"mp": mp_data, "vmp": vmp_data, "dt": timedelta_data},
            )
            return result, ""
        except Exception:
            return None, traceback.format_exc()

    def update_calculated_energy_deltas(
        self, start_datetime=None, end_datetime=None, intervals=None
    ):
        if intervals is None:
            intervals = CalculatedMeteringPointEnergyDeltaInterval.objects.all()

        start_datetime_in = start_datetime
        end_datetime_in = end_datetime
        for interval in intervals:
            datetime_now = pytz.timezone(interval.timezone).localize(datetime.now())
            first_datetime = self.get_first_datetime(default=datetime_now)

            if start_datetime_in is None:
                start_datetime = calculate_start_datetime(first_datetime, interval)

            if end_datetime is None:
                end_datetime = self.get_last_datetime(default=datetime_now)

            timestamps, data = self.eval(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval=interval,
            )

            CalculatedVirtualMeteringPointEnergyDelta.objects.filter(
                virtual_metering_point=self, interval=interval
            ).delete()

            for mp in MeteringPoint.objects.filter(
                pk__in=self.get_mp_ids_from_calculation()
            ):
                if mp.last_precalculation_update is None:
                    mp.update_calculated_energy_deltas(
                        start_datetime=start_datetime_in,
                        end_datetime=end_datetime_in,
                        intervals=intervals,
                    )

            for vmp in VirtualMeteringPoint.objects.filter(
                pk__in=self.get_vmp_ids_from_calculation()
            ):
                if vmp.last_precalculation_update is None:
                    vmp.update_calculated_energy_deltas(
                        start_datetime=start_datetime_in,
                        end_datetime=end_datetime_in,
                        intervals=intervals,
                    )

            new_items = []
            for i in range(len(data)):
                if np.isnan(data[i]) or np.isinf(data[i]):
                    continue
                new_items.append(
                    CalculatedVirtualMeteringPointEnergyDelta(
                        interval=interval,
                        energy_delta=data[i],
                        reading_date=pytz.utc.localize(
                            datetime.utcfromtimestamp(
                                timestamps[i + 1]
                            )  # fix timestamp idx, done
                        ),
                        virtual_metering_point=self,
                    )
                )
            CalculatedVirtualMeteringPointEnergyDelta.objects.bulk_create(new_items)

        self.last_precalculation_update = tz_local.localize(datetime.now())
        self.save()

    def get_first_datetime(self, default=None):

        first_datetime = default

        if self.in_operation_from is not None:
            # if in_operation_from is set limit the first_datetime to that date
            first_datetime = self.in_operation_from

        for vmp_id in self.get_vmp_ids_from_calculation():
            vmp = VirtualMeteringPoint.objects.get(pk=int(vmp_id))
            first_datetime_tmp = vmp.get_first_datetime(
                default=tz_local.localize(datetime.now())
            )
            if type(first_datetime) is datetime:
                if first_datetime_tmp < first_datetime:
                    first_datetime = first_datetime_tmp
            else:
                first_datetime = first_datetime_tmp

        for mp_id in self.get_mp_ids_from_calculation():
            mp = MeteringPoint.objects.get(pk=int(mp_id))
            first_datetime_tmp = mp.get_first_datetime(
                default=tz_local.localize(datetime.now())
            )
            if type(first_datetime) is datetime:
                if first_datetime_tmp < first_datetime:
                    first_datetime = first_datetime_tmp
            else:
                first_datetime = first_datetime_tmp

        return first_datetime

    def get_last_datetime(self, default=None):

        last_datetime = default
        if self.in_operation_to is not None:
            # if in_operation_to is set limit the last_datetime to that date
            last_datetime = self.in_operation_to

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

    def get_related_virtual_metering_points(self):
        vmps = []
        for vmp in VirtualMeteringPoint.objects.all():
            if self.pk in vmp.get_vmp_ids_from_calculation():
                vmps.append(vmp)

        return vmps

    class Meta:
        ordering = ("name",)


class VirtualMeteringPointAttribute(Attribute):
    metering_point = models.ForeignKey(VirtualMeteringPoint, on_delete=models.CASCADE)


class EnergyMeter(models.Model):
    id_ext = models.CharField(max_length=255, blank=True)
    id_int = models.CharField(max_length=255, blank=True)
    comment = models.CharField(max_length=255, default="", blank=True)
    _in_operation_from = models.DateField(null=True, blank=True)
    _in_operation_to = models.DateField(null=True, blank=True)
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

    data_source_variable = models.ForeignKey(
        "VariableDataSource", on_delete=models.SET_NULL, null=True, blank=True
    )

    first_reading = models.ForeignKey(
        "EnergyReading",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="energyreading_first",
    )

    last_reading = models.ForeignKey(
        "EnergyReading",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="energyreading_last",
    )

    def __str__(self):
        metering_point_name = self.metering_point.name if self.metering_point else "-"
        return f"{metering_point_name}({self.pk}) ({self.id_ext}, {self.id_int})"

    @property
    def in_operation_from(self):
        if self._in_operation_from is not None:
            return self._in_operation_from

        if self.metering_point._in_operation_from is not None:
            return self.metering_point._in_operation_from

        return

    @property
    def in_operation_to(self):
        if self._in_operation_to is not None:
            return self._in_operation_to

        if self.metering_point._in_operation_to is not None:
            return self.metering_point._in_operation_to

        return

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

    def interp_readings(
        self,
        start_datetime=None,
        end_datetime=None,
        interval=None,
        timestamps=None,
    ):
        if start_datetime is None and end_datetime is None and timestamps is None:
            return [], []

        if timestamps is None:
            timestamps = calculate_timestamps(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                interval=interval,
            )
        else:
            start_datetime = pytz.utc.localize(datetime.utcfromtimestamp(timestamps[0]))
            end_datetime = pytz.utc.localize(datetime.utcfromtimestamp(timestamps[-1]))

        if start_datetime >= end_datetime or len(timestamps) == 0:
            return [], []

        meter_timestamps, meter_readings = self.get_readings(
            start_datetime=start_datetime
            - relativedelta(
                months=1
            ),  # fixme make dependend on difference between start and stop timestamp
            end_datetime=end_datetime + relativedelta(months=1),
            convert_to_upcounting=True,
        )

        if len(meter_readings) < 2:
            return timestamps, np.zeros((len(timestamps),))

        interp_readings = np.interp(timestamps, meter_timestamps, meter_readings)

        return timestamps, interp_readings

    def energy_data(
        self,
        start_datetime=None,
        end_datetime=None,
        interval=None,
        use_load_profile=False,
        timestamps=None,
    ):
        timestamps, interp_readings = self.interp_readings(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            interval=interval,
            timestamps=timestamps,
        )
        return timestamps, np.diff(interp_readings)

    def check_readings(self):
        meter_timestamps, meter_readings = self.get_readings(convert_to_upcounting=True)

    def get_first_datetime(self, default=None):
        if self.first_reading is None:
            self.first_reading = self.energyreading_set.first()
            self.save()

        if self.first_reading is None:
            if self.in_operation_from is not None:
                return max(
                    default,
                    tz_local.localize(
                        datetime.combine(self.in_operation_from, datetime.min.time())
                    ),
                )
            else:
                return default

        return self.first_reading.reading_date

    def get_last_datetime(self, default=None):
        if self.last_reading is None:
            self.last_reading = self.energyreading_set.last()
            self.save()

        if self.last_reading is None:
            if self.in_operation_to is not None:
                return min(
                    default,
                    tz_local.localize(
                        datetime.combine(self.in_operation_to, datetime.min.time())
                    ),
                )
            else:
                return default
            return default

        return self.last_reading.reading_date

    def import_data_from_data_source(self, dry_run=False):
        if self.data_source_variable is None:
            return

        date_to = datetime.now()
        date_from = self.get_last_datetime(datetime(2016, 1, 1, 0, 0, tzinfo=pytz.utc))
        data = Variable.objects.read_multiple(
            variable_ids=[self.data_source_variable.variable_id],
            time_min=date_from.timestamp(),
            time_max=date_to.timestamp(),
            query_first_value=True,
        )
        data = data[self.data_source_variable.variable_id]
        factor = factor_from_unit(self.data_source_variable.variable.unit.unit)
        last_reading = self.energyreading_set.last()
        old_reading = None
        if last_reading:
            old_reading = float(last_reading.reading)
        plausible = True
        er_data = []

        reading_date = datetime.fromtimestamp(data[0][0] / 1000).replace(
            tzinfo=pytz.timezone("CET")
        )
        to_delete = self.energyreading_set.filter(
            reading_date__gte=reading_date
        ).count()
        if to_delete > 0:
            print(f"deleted old readings {self.pk}: {self} {to_delete}")
            if not dry_run:
                self.energyreading_set.filter(reading_date__gte=reading_date).delete()

        reading = data[0][1] * factor
        print(f"First {reading_date.isoformat()[:19]} {reading}")
        if old_reading is None:
            old_reading = reading

        for i in range(len(data)):
            # read the Unit of the Data from the current Line and convert it to a
            # factor for kWh conversion
            reading_date = datetime.fromtimestamp(data[i][0] / 1000).replace(
                tzinfo=pytz.timezone("CET")
            )
            reading = data[i][1] * factor
            # FIXME check more if reading is plausible

            if i == (len(data) - 1):
                print(f"Last {reading_date.isoformat()[:19]} {reading}")

            if self.meter_type == "upcounting":
                if reading < old_reading:
                    # plausible = False
                    print(
                        f"{reading_date.isoformat()[:19]} {old_reading} > {reading} \
                        is not plausible"
                    )
                    continue

            old_reading = reading

            er = EnergyReading(
                reading_date=reading_date, reading=reading, energy_meter=self
            )
            er_data.append(er)

        if dry_run:
            print(f"would have added {len(er_data)} new readings")

        if not dry_run and plausible:
            EnergyReading.objects.bulk_create(er_data)
            self.update_reading_dates()
            if self.metering_point is not None:
                self.metering_point.last_precalculation_update = None
                self.metering_point.save()
            print(f"added new readings: {len(er_data)}")

    def update_reading_dates(self):
        self.last_reading = self.energyreading_set.last()
        self.first_reading = self.energyreading_set.first()
        self.save()

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

    def __str__(self):
        return f"{self.reading_date.isoformat()} {self.reading} \
                ({self.energy_meter} {self.tariff_register})"

    def save(self, **kwargs):
        super().save(**kwargs)  # Call the "real" save() method.
        if self.energy_meter is None or self.energy_meter.metering_point is None:
            return

        # set the last_precalctulation status of the corresponding MeteringPoint
        # to None to indicate a update of the precalctulated energy deltas of
        # the MeteringPoint is nessesary, this also resets the status for all
        # related VirtualMeteringPoint
        self.energy_meter.metering_point.last_precalculation_update = None
        self.energy_meter.last_reading = None
        self.energy_meter.first_reading = None
        self.energy_meter.metering_point.save()

    def delete(self, **kwargs):
        if self.energy_meter is None or self.energy_meter.metering_point is None:
            return

        # set the last_precalctulation status of the corresponding MeteringPoint
        # to None to indicate a update of the precalctulated energy deltas of
        # the MeteringPoint is nessesary, this also resets the status for all
        # related VirtualMeteringPoint
        self.energy_meter.metering_point.last_precalculation_update = None
        self.energy_meter.metering_point.save()

        super().delete(**kwargs)  # Call the "real" save() method.

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
        help_text="can be hour, day, month, quater, year or duration in seconds",
    )
    timezone_choices = [(item, item) for item in pytz.all_timezones]
    timezone = models.CharField(
        max_length=255, default=settings.TIME_ZONE, choices=timezone_choices
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
        if self.interval_length == "week":
            return "week"
        if self.interval_length == "day":
            return "day"
        if self.interval_length == "hour":
            return 60

        return self.interval_length

    def get_interval_relativedelta(self):
        if self.interval_length == "week":
            return relativedelta(days=7)
        if self.interval_length == "day":
            return relativedelta(days=1)
        if self.interval_length == "hour":
            return relativedelta(hours=1)
        if self.interval_length == "month":
            return relativedelta(months=1)
        if self.interval_length == "quater":
            return relativedelta(months=3)
        if self.interval_length == "year":
            return relativedelta(years=1)
        return relativedelta(seconds=self.interval_length)

    def __str__(self):
        return f"{self.interval_length} {self.timezone}"


class CalculatedMeteringPointEnergyDeltaProto(models.Model):
    """ """

    interval = models.ForeignKey(
        CalculatedMeteringPointEnergyDeltaInterval, on_delete=models.CASCADE
    )
    energy_delta = EnergyValue()
    reading_date = models.DateTimeField(db_index=True)  # timestamp of the reading

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


"""
class WithNoName(models.Model):
    interval = models.ForeignKey(
        CalculatedMeteringPointEnergyDeltaInterval, on_delete=models.CASCADE
    )
    interval = models.ForeignKey(
        MeteringPoint, on_delete=models.CASCADE, null=True, blank=True
    )
    interval = models.ForeignKey(
        VirtualMeteringPoint, on_delete=models.CASCADE, null=True, blank=True
    )
    calculation_date = models.DateTimeField(null=True, blank=True)  # timestamp
    # of the reading
"""


class VariableDataSource(models.Model):
    variable = models.ForeignKey(
        Variable,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return f"{self.variable}"


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
    periode_from = models.DateTimeField(
        help_text=(
            "this will be interpreted as local time"
            " in the local that is set in the interval_length field"
        )
    )
    periode_to = models.DateTimeField(
        help_text=(
            "this will be interpreted as local time"
            " in the local that is set in the interval_length field"
        )
    )
    interval = models.ForeignKey(
        CalculatedMeteringPointEnergyDeltaInterval, on_delete=models.CASCADE
    )

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

    def __str__(self):
        return (
            self.label
            + "_"
            + make_local_native(self.periode_from, self.interval.timezone).isoformat()
            + "_"
            + make_local_native(self.periode_to, self.interval.timezone).isoformat()
            + "_"
            + str(self.interval).replace(" ", "_")
        )

    @property
    def full_filename(self):
        filename = self.export_file_name

        if filename == "":
            filename = self.label.replace(" ", "_")
            filename += "_"
            filename += make_local_native(
                self.periode_from, self.interval.timezone
            ).isoformat()
            filename += "_"
            filename += make_local_native(
                self.periode_to, self.interval.timezone
            ).isoformat()
            filename += "_"
            filename += self.interval.timezone
        filename += "." + self.file_format

        return filename

    def prepare_data(self):
        """ """
        target_timezone_name = self.interval.timezone
        datetime_from = (
            self.periode_from
        )  # todo convert to timestamp that matches the interval_length
        datetime_to = (
            self.periode_to
        )  # todo convert to timestamp that matches the interval_length
        timestamps = calculate_timestamps(
            datetime_from, datetime_to, interval=self.interval
        )

        # Header
        header = []
        header.append("label")
        header.append("utility")
        header.append("unit")
        header.append("ID")
        header.append("model")
        header.append("categories")
        attribute_keys = self.attribute_keys.all()

        for key in attribute_keys:
            header.append(key.name)

        header.append("Source Points")

        for timestamp in timestamps[1:]:
            # add one column per timestamp
            dp_date = pytz.timezone(target_timezone_name).localize(
                datetime.utcfromtimestamp(timestamp)
            )

            if self.file_format == "csv":
                header.append(dp_date.isoformat())

            elif self.file_format == "xlsx":
                # convert to non aware local datetime
                dp_date = (
                    pytz.utc.localize(datetime.utcfromtimestamp(timestamp))
                    .astimezone(pytz.timezone(target_timezone_name))
                    .replace(tzinfo=None)
                )
                header.append(dp_date)

            else:
                header.append(dp_date)

        data = []
        for mp in self.metering_points.all():
            data_row = []

            data_row.append(mp.name)  # label/name
            data_row.append(mp.utility.name)  #
            data_row.append(mp.unit.unit if mp.unit is not None else "-")  # unit
            data_row.append(mp.pk)  # ID
            data_row.append("mp")  # model (mp, vmp)
            data_row.append(
                ", ".join(list(mp.categories.all().values_list("name", flat=True)))
            )  # categories

            for key in attribute_keys:
                mp_attr = mp.meteringpointattribute_set.filter(key=key).first()
                if mp_attr is None:
                    data_row.append("-")
                else:
                    data_row.append(mp_attr.value)  # todo escape delimiter Char

            data_row.append("-")  # Source Points, tbd
            mp_data = mp.energy_data(timestamps=timestamps, interval=self.interval)[1]
            for value in mp_data:
                data_row.append(value)

            data.append(data_row)

        for mp in self.virtual_metering_points.all():
            data_row = []

            data_row.append(mp.name)  # label/name
            data_row.append(mp.utility.name)  #
            data_row.append(mp.unit.unit if mp.unit is not None else "-")  # unit
            data_row.append(mp.pk)  # ID
            data_row.append("vmp")  # Model (mp, vmp)
            data_row.append(
                " ".join(list(mp.categories.all().values_list("name", flat=True)))
            )  # categories

            for key in attribute_keys:
                mp_attr = mp.virtualmeteringpointattribute_set.filter(key=key).first()
                if mp_attr is None:
                    data_row.append("-")
                else:
                    data_row.append(mp_attr.value)  # todo escape delimiter Char

            data_row.append("-")  # Source Points, tbd
            mp_data = mp.energy_data(timestamps=timestamps, interval=self.interval)[1]
            for value in mp_data:
                data_row.append(value)

            data.append(data_row)

        return header, data

    def make_file(self, file_path, header=None, data=None):
        """"""
        buffer = self.make_buffer(header, data)
        if buffer is None:
            return False

        with open(os.path.join(file_path, self.full_filename), "wb") as f:
            f.write(buffer.getbuffer())
        return True

    def make_buffer(self, header=None, data=None):

        if self.file_format == "csv":
            return self.generate_csv(header, data)

        if self.file_format == "xlsx":
            return self.generate_xlsx(header, data)

        if self.file_format == "json":
            return self.generate_json(header, data)

        return None

    def generate_csv(self, header=None, data=None):
        """ """
        if header is None or data is None:
            header, data = self.prepare_data()

        buffer = io.StringIO()

        csv_writer = csv.writer(buffer)

        # write the header
        csv_writer.writerow(header)

        # write the data
        for row in range(len(data)):
            csv_writer.writerow(data[row])

        return buffer

    def generate_xlsx(self, header=None, data=None):
        """ """
        if header is None or data is None:
            header, data = self.prepare_data()

        buffer = io.BytesIO()

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

        if value_col is None:
            workbook.close()
            return buffer

        # write the data
        for row_num, row_values in enumerate(data):
            for col_num, value in enumerate(row_values):
                if col_num >= value_col:
                    worksheet.write(row_num + 1, col_num, value, energy_format)
                else:
                    worksheet.write(row_num + 1, col_num, value)

        workbook.close()
        return buffer

    def generate_json(self, header=None, data=None):
        """ """
        if header is None or data is None:
            header, data = self.prepare_data()

        buffer = io.StringIO()

        output = {}
        for row_num, row_values in enumerate(data):
            row_key = f"{row_values[3]}_{row_values[2]}"
            output[row_key] = {}
            for col_num, value in enumerate(row_values):
                if type(header[col_num]) is datetime:
                    output[row_key][header[col_num].isoformat()] = value
                else:
                    output[row_key][header[col_num]] = value

        json.dump(output, buffer)
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
