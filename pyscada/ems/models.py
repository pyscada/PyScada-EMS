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


class Utility(ListElement):
    pass


class BuildingCategory(ListElement):
    pass


class Address(models.Model):
    street = models.CharField(max_length=255)
    zip = models.CharField(max_length=10)
    town = models.CharField(max_length=255)
    def __str__(self):
        return "%s, %s, %s"%(self.street,self.zip, self.town)

    class Meta:
        ordering = ["street"]


class BuildingInfo(models.Model):
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


class Building(models.Model):
    number = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=25)
    contruction_date = models.DateField()
    category = models.ForeignKey(BuildingCategory, on_delete=models.CASCADE)
    site = models.CharField(max_length=255)
    info = models.ManyToManyField(BuildingInfo)
    address = models.ForeignKey(Address, on_delete=models.CASCADE, null=True)
    comment = models.TextField(blank=True, default="")
    def __str__(self):
            return "%s (%d)"%(self.short_name, self.number)


class MaLoID(models.Model):
    malo_id = models.CharField(max_length=11)
    address = models.ForeignKey(Address, on_delete=models.CASCADE, null=True)
    def __str__(self):
            return f"{self.malo_id}"


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


class MeteringPointProto(models.Model):
    name = models.CharField(max_length=255, blank=True, default="")
    utility = models.ForeignKey(Utility, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.CharField(max_length=255,default="", blank=True)
    melo = models.CharField(max_length=33, blank=True, default="DE")
    malo = models.ForeignKey(MaLoID, on_delete=models.CASCADE, null=True, blank=True)
    in_operation_from = models.DateField(null=True, blank=True)
    in_operation_to = models.DateField(null=True, blank=True)
    class Meta:
        abstract = True
        ordering = ('name',)


class MeteringPoint(MeteringPointProto):
    location = models.ManyToManyField(Building, blank=True)
    higher_level_metering_points = models.ManyToManyField("MeteringPoint", blank=True)
    def __str__(self):
            return f"{self.name}, {', '.join(list(self.energymeter_set.all().values_list('id_int_old',flat=True)))}"

    class Meta:
        ordering = ('name',)


class MeteringPointAttribute(Attribute):
    metering_point = models.ForeignKey(MeteringPoint, on_delete=models.CASCADE)


class CalulationSource(models.Model):
    name = models.CharField(max_length=10)
    parent = models.ForeignKey("VirtualMeteringPoint", on_delete=models.CASCADE)

    metering_point =  models.ForeignKey(MeteringPoint, on_delete=models.CASCADE, blank=True, null=True)
    virtual_metering_point =  models.ForeignKey("VirtualMeteringPoint", on_delete=models.CASCADE, blank=True, null=True, related_name="virtual_metering_point_source")
    metering_point_dp_name = models.CharField(max_length=255, blank=True, default="")



class VirtualMeteringPoint(MeteringPointProto):
    calculation = models.TextField(default="", blank=True)
    in_operation_from = models.DateField(null=True, blank=True)
    in_operation_to = models.DateField(null=True, blank=True)

    def __str__(self):
            return f"{self.name}"

    class Meta:
        ordering = ('name',)


class VirtualMeteringPointAttribute(Attribute):
    metering_point = models.ForeignKey(VirtualMeteringPoint, on_delete=models.CASCADE)


class EnergyMeter(models.Model):
    id_ext = models.CharField(max_length=255, blank=True)
    id_int_old = models.CharField(max_length=255, blank=True)
    id_int = models.BigIntegerField(blank=True, default=0)
    comment = models.CharField(max_length=255,default="", blank=True)
    in_operation_from = models.DateField(null=True, blank=True)
    in_operation_to = models.DateField(null=True, blank=True)
    metering_point = models.ForeignKey(MeteringPoint, on_delete=models.CASCADE, null=True, blank=True)
    factor = models.FloatField(default=1, blank=True)
    def __str__(self):
            return f"{self.metering_point.name if self.metering_point else '-'} ({self.id_ext}, {self.id_int})"


class EnergyMeterVariableValueType(ListElement):
    pass


class EnergyMeterAttribute(Attribute):
    energy_meter = models.ForeignKey(EnergyMeter, on_delete=models.CASCADE)


class EnergyMeterDataPoint(models.Model):
    value_type = models.ForeignKey(EnergyMeterVariableValueType, on_delete=models.CASCADE)
    energy_meter = models.ForeignKey(EnergyMeter, on_delete=models.CASCADE)
    variable = models.OneToOneField(Variable, on_delete=models.CASCADE)
    def __str__(self):
        if self.variable.short_name != '':
            return f"{self.energy_meter.metering_point.name}-{self.variable.name}-{self.variable.short_name}-{self.value_type}"
        return f"{self.energy_meter.metering_point.name}-{self.variable.name}-{self.value_type}"

    @property
    def label(self):
        return self.variable.short_name or self.energy_meter.metering_point.name


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
    data_point = models.ForeignKey(EnergyMeterDataPoint, on_delete=models.CASCADE)

    def web_id(self):
        return f"ems_form-{self.form.id.__str__()}-{self.id.__str__()}"

    def web_label(self):
        return self.label or self.data_point.label

    def web_unit(self):
        return self.data_point.variable.unit.unit

    def previous_value(self):
        return 1234

    def previous_time(self):
        return "2011-11-11T11:11"

    def __str__(self):
        return f"{self.label}({self.position})"

    class Meta:
        ordering = ["position"]