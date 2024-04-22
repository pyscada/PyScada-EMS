# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from pyscada.models import Unit, Variable


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


class AttributeKey(ListElement):
    show_in_meteringpoint_admin = models.BooleanField(default=False)
    show_in_energymeter_admin = models.BooleanField(default=False)

    show_from_mp_in_em_admin = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}({self.pk})"


class Attribute(models.Model):
    key = models.ForeignKey(AttributeKey, on_delete=models.CASCADE, null=True)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.value}"

    class Meta:
        abstract = True
        ordering = ["key"]

class Location(models.Model):
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
    def __str__(self):
        return f"{self.name} ({self.utility.name if self.utility else '-'})"

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
    def __str__(self):
        return f"{self.metering_point.name if self.metering_point else '-'}({self.pk}) ({self.id_ext}, {self.id_int})"


class EnergyMeterVariableValueType(ListElement):
    pass


class EnergyMeterAttribute(Attribute):
    energy_meter = models.ForeignKey(EnergyMeter, on_delete=models.CASCADE)


class EnergyReading(models.Model):
    reading_date = models.DateTimeField(blank=True, null=True, db_index=True) # timestamp of the reading
    reading = EnergyValue(default=0, blank=True) # upcountig meterreading
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
