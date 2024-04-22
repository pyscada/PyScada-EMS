from django.contrib import admin
from pyscada.admin import admin_site

from pyscada.ems.models import *
from pyscada.models import Device, RecordedData, Variable


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


class CalulationSourceInline(admin.StackedInline):
    model = CalulationSource
    fk_name = "parent"
    extra = 0


class EnergyMeterVariableInline(admin.StackedInline):
    model = EnergyMeterVariable
    extra = 0


class DataEntryFormElementInline(admin.StackedInline):
    model = DataEntryFormElement
    extra = 0
    ordering = ("position",)


class EnergyMeterAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "dp_count",
        "id_ext",
        "id_int_pp",
        "id_int_old",
        "factor",
        "comment",
        "in_operation_from",
        "in_operation_to",
    )
    list_display_links = ("id",)
    list_editable = ("comment",)
    list_filter = []
    search_fields = ["id_ext", "id_int_old", "comment", "metering_point__name"]
    save_as = True
    save_as_continue = True
    inlines = [EnergyMeterAttributeInline, EnergyMeterVariableInline]
    try:
        for attribute_key in AttributeKey.objects.filter(
            show_in_energymeter_admin=True
        ):

            @admin.display(description=attribute_key.name)
            def get_attribute_key(instance, key_name=attribute_key.name):
                return instance.energymeterattribute_set.filter(
                    key__name=key_name
                ).first()

            list_display += (get_attribute_key,)

        for attribute_key in AttributeKey.objects.filter(show_from_mp_in_em_admin=True):

            @admin.display(description=f"MP {attribute_key.name}")
            def get_mp_attribute_key(instance, key_name=attribute_key.name):
                return instance.metering_point.meteringpointattribute_set.filter(
                    key__name=key_name
                ).first()

            list_display += (get_mp_attribute_key,)
    except:
        pass

    def dp_count(self, instance):
        return RecordedData.objects.filter(variable_id=instance.pk).count()

    def id_int_pp(self, instance):
        return add_spaces(f"{instance.id_int}", [2, 6, 11])


class MeteringPointAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "is_sub_meter",
        "energy_meters",
        "utility",
        "comment",
    )
    try:
        for attribute_key in AttributeKey.objects.filter(
            show_in_meteringpoint_admin=True
        ):

            @admin.display(description=attribute_key.name)
            def get_attribute_key(instance, key_name=attribute_key.name):
                return instance.meteringpointattribute_set.filter(
                    key__name=key_name
                ).first()

            list_display += (get_attribute_key,)
    except:
        pass

    list_display_links = ("id",)
    list_editable = ("comment",)
    filter_horizontal = (
        "location",
        "higher_level_metering_points",
    )
    list_filter = [
        "utility",
    ]
    search_fields = [
        "name",
        "comment",
    ]
    save_as = True
    save_as_continue = True
    inlines = [EnergyMeterInline, MeteringPointAttributeInline]

    def is_sub_meter(self, instance):
        return instance.higher_level_metering_points.count() > 0

    def energy_meters(self, instance):
        return f"{', '.join(list(instance.energymeter_set.all().values_list('id_int_old',flat=True)))}, {', '.join(list(instance.energymeter_set.all().values_list('id_ext',flat=True)))}"


class VirtualMeteringPointAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "utility", "category", "comment")
    list_display_links = ("id",)
    list_editable = ("comment",)
    list_filter = ["utility", "category"]
    search_fields = [
        "name",
        "comment",
    ]
    save_as = True
    save_as_continue = True
    inlines = [VirtualMeteringPointAttributeInline, CalulationSourceInline]


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
    list_display_links = ("id",)
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


class DataEntryFormAdmin(admin.ModelAdmin):
    inlines = [DataEntryFormElementInline]


class EnergyMeterVariableAdmin(admin.ModelAdmin):
    autocomplete_fields = ("energy_meter",)

    def get_form(self, request, obj=None, **kwargs):
        form = super(EnergyMeterVariableAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields["variable"].queryset = Variable.objects.filter(
            energymetervariable=None
        )  # Only show variables that are not already connected to a energymeterdatapoint
        if obj is not None:
            form.base_fields["variable"].queryset |= Variable.objects.filter(
                pk=obj.variable_id
            )  # add the selected value if ther is none
        return form


admin_site.register(EnergyMeter, EnergyMeterAdmin)
admin_site.register(MeteringPoint, MeteringPointAdmin)
admin_site.register(Address, AddressAdmin)
admin_site.register(BuildingInfo, BuildingInfoAdmin)
admin_site.register(BuildingCategory, BuildingCategoryAdmin)
admin_site.register(Building, BuildingAdmin)
admin_site.register(Utility, UtilityAdmin)
admin_site.register(VirtualMeteringPointCategory, VirtualMeteringPointCategoryAdmin)
admin_site.register(MaLoID)
admin_site.register(AttributeKey)
admin_site.register(EnergyMeterVariable, EnergyMeterVariableAdmin)
admin_site.register(EnergyMeterVariableValueType)
admin_site.register(VirtualMeteringPoint, VirtualMeteringPointAdmin)
admin_site.register(DataEntryForm, DataEntryFormAdmin)
