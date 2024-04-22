from django.contrib import admin
from django.db.models import Count
from django.db.models import Case, When

from pyscada.admin import admin_site
from pyscada.ems.models import *
from pyscada.models import Device, RecordedData, Variable

import traceback
import logging

logger = logging.getLogger(__name__)



def add_spaces(wstr, sp_pos):
    """adds spaces into wstr at sp_pos positions
    01234567, [2,4] ->  01 23 4567
    """
    offset = 0
    for i in sp_pos:
        if (i + offset) >= len(wstr):
            continue
        wstr = wstr[: (i + offset)] + " " + wstr[(i + offset) :]
        offset += 1
    return wstr


def get_metering_point_attribute_key(instance, key_name):
    return


def get_meteringpoint_ordering_by_attribute_key(key_id):
    key_ids = list(MeteringPoint.objects.filter(meteringpointattribute__key_id=key_id).order_by("meteringpointattribute__value").values_list("pk",flat=True))

    preferred = Case(
        *(
            When(pk=id, then=pos)
            for pos, id in enumerate(key_ids, start=1)
        )
    )
    return preferred

def get_enegrymeter_ordering_by_attribute_key(key_id):
    key_ids = list(EnergyMeter.objects.filter(energymeterattribute__key_id=key_id).order_by("energymeterattribute__value").values_list("pk",flat=True))

    preferred = Case(
        *(
            When(pk=id, then=pos)
            for pos, id in enumerate(key_ids, start=1)
        )
    )
    return preferred

def get_enegrymeter_ordering_by_meteringpoint_attribute_key(key_id):
    key_ids = list(EnergyMeter.objects.filter(metering_point__meteringpointattribute__key_id=key_id).order_by("metering_point__meteringpointattribute__value").values_list("pk",flat=True))

    preferred = Case(
        *(
            When(pk=id, then=pos)
            for pos, id in enumerate(key_ids, start=1)
        )
    )
    return preferred

class IsSubMeterFilter(admin.SimpleListFilter):
    title = 'is sub meter'
    parameter_name = 'is sub meter'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        queryset = queryset.annotate(higher_level_metering_points_count=Count('higher_level_metering_points'))
        if value == 'Yes':
            return queryset.filter(higher_level_metering_points_count__gt=0)
        elif value == 'No':
            return queryset.exclude(higher_level_metering_points_count__gt=0)
        return queryset

class EnergyMeterInline(admin.StackedInline):
    model = EnergyMeter
    extra = 0


class EnergyMeterAttributeInline(admin.StackedInline):
    model = EnergyMeterAttribute
    extra = 0


class MeteringPointAttributeInline(admin.StackedInline):
    model = MeteringPointAttribute
    extra = 0


class VirtualMeteringPointAttributeInline(admin.StackedInline):
    model = VirtualMeteringPointAttribute
    extra = 0


class DataEntryFormElementInline(admin.StackedInline):
    model = DataEntryFormElement
    extra = 0
    ordering = ("position",)

class BuildingInfoInline(admin.StackedInline):
    model = BuildingInfo
    extra = 0

class EnergyMeterAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "dp_count",
        "id_ext",
        "id_int",
        "factor",
        "comment",
        "in_operation_from",
        "in_operation_to",
    )
    list_display_links = ("id",)
    list_editable = ("comment",)
    list_filter = ["metering_point__utility"]
    search_fields = ["id_ext", "comment", "metering_point__name"]
    save_as = True
    save_as_continue = True
    inlines = [EnergyMeterAttributeInline]

    def dp_count(self, instance):
        return EnergyReading.objects.filter(energy_meter_id=instance.pk).count()

    try:
        for attribute_key in AttributeKey.objects.filter(
            show_in_energymeter_admin=True
        ):

            @admin.display(description=attribute_key.name, ordering=get_enegrymeter_ordering_by_attribute_key(attribute_key.pk))
            def get_attribute_key(instance, key_name=attribute_key.name):
                return instance.energymeterattribute_set.filter(
                    key__name=key_name
                ).first()

            list_display += (get_attribute_key,)

        for attribute_key in AttributeKey.objects.filter(show_from_mp_in_em_admin=True):

            @admin.display(description=f"MP {attribute_key.name}", ordering=get_enegrymeter_ordering_by_meteringpoint_attribute_key(attribute_key.pk))
            def get_mp_attribute_key(instance, key_name=attribute_key.name):
                return instance.metering_point.meteringpointattribute_set.filter(
                    key__name=key_name
                ).first()

            list_display += (get_mp_attribute_key,)
    except:
        logger.warning(traceback.format_exc())


class EnergyReadingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reading_date",
        "reading",
        "energy_meter",
    )
    list_filter = (
        "energy_meter",
    )


class MeteringPointAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "dp_count",
        "name",
        "is_sub_meter",
        "energy_meters",
        "utility",
        "comment",
    )
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(higher_level_metering_points_count=Count('higher_level_metering_points'))
        return qs

    @admin.display(ordering="higher_level_metering_points_count")
    def is_sub_meter(self, instance):
        return instance.higher_level_metering_points_count > 0
    is_sub_meter.boolean = True

    @admin.display
    def energy_meters(self, instance):
        return f"{', '.join(list(instance.energymeter_set.all().values_list('id_int',flat=True)))}, {', '.join(list(instance.energymeter_set.all().values_list('id_ext',flat=True)))}"

    def dp_count(self, instance):
        count = 0
        for energy_meter in instance.energymeter_set.all():
            count += EnergyReading.objects.filter(energy_meter_id=energy_meter.pk).count()
        return count

    try:
        for attribute_key in AttributeKey.objects.filter(
            show_in_meteringpoint_admin=True
        ):

            @admin.display(description=attribute_key.name, ordering=get_meteringpoint_ordering_by_attribute_key(attribute_key.pk))
            def get_attribute_key(instance, key_name=attribute_key.name):
                return instance.meteringpointattribute_set.filter(
                    key__name=key_name
                ).first()

            list_display += (get_attribute_key,)
    except:
        logger.warning(traceback.format_exc())

    list_display_links = ("id",)
    list_editable = ("comment",)
    filter_horizontal = (
        "higher_level_metering_points",
    )
    list_filter = [
        "utility",
        IsSubMeterFilter,
    ]
    search_fields = [
        "name",
        "comment",
    ]
    save_as = True
    save_as_continue = True
    inlines = [EnergyMeterInline, MeteringPointAttributeInline]


class VirtualMeteringPointAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "utility", "category", "group", "comment")
    list_display_links = ("id",)
    list_editable = ("comment",)
    list_filter = [ "utility",
                    "category",
                    "group",]
    search_fields = [
        "name",
        "comment",
    ]
    save_as = True
    save_as_continue = True
    inlines = [VirtualMeteringPointAttributeInline]


class BuildingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "short_name",
        "number",
        "name",
        "contruction_date",
        "category",
        "site",
    )  # 'address__street', 'address__zip', 'address__town')
    list_display_links = (
        "id",
        "short_name",
    )
    # list_editable = ('name', 'contruction_date', 'category', 'site', )
    # filter_horizontal = ('short_name','number', 'name', 'contruction_date', 'category__name', 'site', 'address__street', 'address__zip', 'address__town')
    save_as = True
    save_as_continue = True
    inlines = [BuildingInfoInline]


class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "street",
        "zip",
        "town",
    )
    list_display_links = ("id",)
    # list_editable = ('street', 'zip', 'town', )
    # filter_horizontal = ('street', 'zip', 'town', )
    save_as = True
    save_as_continue = True


class BuildingInfoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "periode_from",
        "periode_to",
        "cost_unit",
        "owner",
        "area_net",
        "area_HNF_1_6",
        "area_NNF_7",
        "area_FF_8",
        "area_VF_9",
        "nb_floors",
        "nb_rooms",
    )
    list_display_links = ("id", "cost_unit")
    # list_editable = ()
    # filter_horizontal = ()
    save_as = True
    save_as_continue = True


class BuildingCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
    )
    list_display_links = ("id",)
    # list_editable = ('name',)
    # filter_horizontal = ('name',)
    save_as = True
    save_as_continue = True


class UtilityAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
    )
    list_display_links = ("name",)
    # list_editable = ('name',)
    # filter_horizontal = ('name',)
    save_as = True
    save_as_continue = True


class VirtualMeteringPointCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
    )
    list_display_links = ("id",)
    # list_editable = ('name',)
    # filter_horizontal = ('name',)
    save_as = True
    save_as_continue = True

class VirtualMeteringPointGroupAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
    )
    list_display_links = ("id",)
    # list_editable = ('name',)
    # filter_horizontal = ('name',)
    save_as = True
    save_as_continue = True

class DataEntryFormAdmin(admin.ModelAdmin):
    inlines = [DataEntryFormElementInline]



admin_site.register(EnergyMeter, EnergyMeterAdmin)
admin_site.register(MeteringPoint, MeteringPointAdmin)
admin_site.register(Address, AddressAdmin)
admin_site.register(BuildingInfo, BuildingInfoAdmin)
admin_site.register(BuildingCategory, BuildingCategoryAdmin)
admin_site.register(Building, BuildingAdmin)
admin_site.register(Location)
admin_site.register(EnergyReading, EnergyReadingAdmin)
admin_site.register(Utility, UtilityAdmin)

admin_site.register(AttributeKey)
admin_site.register(VirtualMeteringPoint, VirtualMeteringPointAdmin)
admin_site.register(VirtualMeteringPointCategory, VirtualMeteringPointCategoryAdmin)
admin_site.register(VirtualMeteringPointGroup, VirtualMeteringPointGroupAdmin)
admin_site.register(DataEntryForm, DataEntryFormAdmin)
