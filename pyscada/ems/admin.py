import logging
import traceback

from django.contrib import admin, messages
from django.db.models import Case, Count, When
from django.http import HttpResponse
from django.template import RequestContext, Template
from django.utils.safestring import mark_safe

try:
    from django_admin_multi_select_filter.filters import (
        ExclusiveMultiSelectRelatedFieldListFilter,
    )
except (ImportError, ModuleNotFoundError):
    ExclusiveMultiSelectRelatedFieldListFilter = None

from pyscada.admin import admin_site
from pyscada.ems.models import (
    Address,
    Attachment,
    AttachmentCategory,
    AttachmentGroup,
    AttributeKey,
    Building,
    BuildingCategory,
    BuildingInfo,
    CalculatedMeteringPointEnergyDelta,
    CalculatedMeteringPointEnergyDeltaInterval,
    CalculatedVirtualMeteringPointEnergyDelta,
    CalculationUnitArea,
    CalculationUnitAreaAttribute,
    CalculationUnitAreaPart,
    CalculationUnitAreaPeriod,
    DataEntryForm,
    DataEntryFormElement,
    DataExport,
    DataImport,
    EnergyMeter,
    EnergyMeterAttachment,
    EnergyMeterAttribute,
    EnergyPrice,
    EnergyPricePeriod,
    EnergyReading,
    EnergyReadingComment,
    EnergyReadingTariffRegister,
    FloatAttributeKey,
    MeteringPoint,
    MeteringPointAttachment,
    MeteringPointAttribute,
    MeteringPointCategory,
    MeteringPointLocation,
    Utility,
    VariableDataSource,
    VirtualMeteringPoint,
    VirtualMeteringPointAttachment,
    VirtualMeteringPointAttribute,
    VirtualMeteringPointCategory,
    VirtualMeteringPointGroup,
    WeatherAdjustment,
    WeatherAdjustmentPeriod,
)

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
    key_ids = list(
        MeteringPoint.objects.filter(meteringpointattribute__key_id=key_id)
        .order_by("meteringpointattribute__value")
        .values_list("pk", flat=True)
    )

    preferred = Case(
        *(When(pk=id, then=pos) for pos, id in enumerate(key_ids, start=1))
    )
    return preferred


def get_enegrymeter_ordering_by_attribute_key(key_id):
    key_ids = list(
        EnergyMeter.objects.filter(energymeterattribute__key_id=key_id)
        .order_by("energymeterattribute__value")
        .values_list("pk", flat=True)
    )

    preferred = Case(
        *(When(pk=id, then=pos) for pos, id in enumerate(key_ids, start=1))
    )
    return preferred


def get_enegrymeter_ordering_by_meteringpoint_attribute_key(key_id):
    key_ids = list(
        EnergyMeter.objects.filter(
            metering_point__meteringpointattribute__key_id=key_id
        )
        .order_by("metering_point__meteringpointattribute__value")
        .values_list("pk", flat=True)
    )

    preferred = Case(
        *(When(pk=id, then=pos) for pos, id in enumerate(key_ids, start=1))
    )
    return preferred


@admin.action(description="Delete selected without conformaition!")
def delete_item_without_confirm(modeladmin, request, queryset):
    for item in queryset.all():
        item.delete()


@admin.action(description="Update calculated energy deltas")
def update_calculated_energy_deltas(modeladmin, request, queryset):
    if queryset.count() <= 10:
        for mp in queryset.all():
            mp.start_precalculation_background_process()
    else:
        queryset.first().start_precalculation_background_process(
            [mp.pk for mp in queryset.all()]
        )
    messages.success(
        request,
        "The Precalculation for the requested MeteringPoints has been started in a Background Process, this will take some time to finish!",  # noqa: E501
    )
    # return HttpResponseRedirect("/pyscada_admin/pyscada/backgroundprocess/")


@admin.action(description="Import data from data source")
def import_data_from_data_source(modeladmin, request, queryset):
    for mp in queryset.all():
        mp.import_data_from_data_source()


@admin.action(description="Download Data (only one selection)")
def download_data(modeladmin, request, queryset):
    dx = queryset.first()
    header, data = dx.prepare_data()
    buffer = dx.make_buffer(header, data)

    if dx.file_format == "csv":
        content_type = "application/csv"
    elif dx.file_format == "xlsx":
        content_type = "application/xlsx"
    elif dx.file_format == "xlsx":
        content_type = "application/json"
    else:
        return None  # todo throw error

    return HttpResponse(
        buffer.getvalue(),
        headers={
            "Content-Type": content_type,
            "Content-Disposition": 'attachment; filename="%s"' % dx.full_filename,
        },
    )


class IsSubMeterFilter(admin.SimpleListFilter):
    title = "is sub meter"
    parameter_name = "is sub meter"

    def lookups(self, request, model_admin):
        return (
            ("Yes", "Yes"),
            ("No", "No"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        queryset = queryset.annotate(
            higher_level_metering_points_count=Count("higher_level_metering_points")
        )
        if value == "Yes":
            return queryset.filter(higher_level_metering_points_count__gt=0)
        elif value == "No":
            return queryset.exclude(higher_level_metering_points_count__gt=0)
        return queryset


class HasCommentFilter(admin.SimpleListFilter):
    title = "has comment"
    parameter_name = "has comment"

    def lookups(self, request, model_admin):
        return (
            ("Yes", "Yes"),
            ("No", "No"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        queryset = queryset.annotate(
            energyreadingcomment_count=Count("energyreadingcomment")
        )
        if value == "Yes":
            return queryset.filter(energyreadingcomment_count__gt=0)
        elif value == "No":
            return queryset.exclude(energyreadingcomment_count__gt=0)
        return queryset


class EnergyMeterInline(admin.StackedInline):
    model = EnergyMeter
    extra = 0
    show_change_link = True
    readonly_fields = ["first_reading", "last_reading"]


class EnergyMeterAttributeInline(admin.StackedInline):
    model = EnergyMeterAttribute
    extra = 0
    show_change_link = True


class MeteringPointAttributeInline(admin.StackedInline):
    model = MeteringPointAttribute
    extra = 0
    show_change_link = True


class VirtualMeteringPointAttributeInline(admin.StackedInline):
    model = VirtualMeteringPointAttribute
    extra = 0
    show_change_link = True


class DataEntryFormElementInline(admin.StackedInline):
    model = DataEntryFormElement
    extra = 0
    ordering = ("position",)
    show_change_link = True


class BuildingInfoInline(admin.StackedInline):
    model = BuildingInfo
    extra = 0
    show_change_link = True


class CalculationUnitAreaPeriodInline(admin.StackedInline):
    model = CalculationUnitAreaPeriod
    extra = 0
    show_change_link = True


class CalculationUnitAreaPartInline(admin.StackedInline):
    model = CalculationUnitAreaPart
    extra = 0
    show_change_link = True


class WeatherAdjustmentPeriodInline(admin.StackedInline):
    model = WeatherAdjustmentPeriod
    extra = 0
    show_change_link = True


class CalculationUnitAreaAttributeInline(admin.StackedInline):
    model = CalculationUnitAreaAttribute
    extra = 0
    show_change_link = True


class EnergyPricePeriodInline(admin.StackedInline):
    model = EnergyPricePeriod
    extra = 0
    show_change_link = True


class MeteringPointAttachmentInline(admin.StackedInline):
    model = MeteringPointAttachment
    extra = 0
    show_change_link = True


class VirtualMeteringPointAttachmentInline(admin.StackedInline):
    model = VirtualMeteringPointAttachment
    extra = 0
    show_change_link = True


class EnergyMeterAttachmentInline(admin.StackedInline):
    model = EnergyMeterAttachment
    extra = 0
    show_change_link = True


class EnergyReadingCommentInline(admin.StackedInline):
    model = EnergyReadingComment
    extra = 0
    show_change_link = True


class EnergyMeterAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "dp_count",
        "id_ext",
        "id_int",
        "factor",
        "comment",
        "_in_operation_from",
        "_in_operation_to",
    )
    list_display_links = ("id", "id_ext")
    list_editable = ("comment",)
    list_filter = ["metering_point__utility", "meter_type"]
    readonly_fields = ["first_reading", "last_reading"]
    search_fields = ["id_ext", "comment", "metering_point__name"]
    save_as = True
    save_as_continue = True
    inlines = [EnergyMeterAttributeInline, EnergyMeterAttachmentInline]
    actions = [import_data_from_data_source]

    def dp_count(self, instance):
        return EnergyReading.objects.filter(energy_meter_id=instance.pk).count()

    try:
        for attribute_key in AttributeKey.objects.filter(
            show_in_energymeter_admin=True
        ):

            @admin.display(
                description=attribute_key.name,
                ordering=get_enegrymeter_ordering_by_attribute_key(attribute_key.pk),
            )
            def get_attribute_key(instance, key_name=attribute_key.name):
                return instance.energymeterattribute_set.filter(
                    key__name=key_name
                ).first()

            list_display += (get_attribute_key,)

        for attribute_key in AttributeKey.objects.filter(show_from_mp_in_em_admin=True):

            @admin.display(
                description=f"MP {attribute_key.name}",
                ordering=get_enegrymeter_ordering_by_meteringpoint_attribute_key(
                    attribute_key.pk
                ),
            )
            def get_mp_attribute_key(instance, key_name=attribute_key.name):
                if instance.metering_point is None:
                    return None
                return instance.metering_point.meteringpointattribute_set.filter(
                    key__name=key_name
                ).first()

            list_display += (get_mp_attribute_key,)

    except Exception:  # fixme
        logger.warning(traceback.format_exc())


class EnergyReadingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reading_date",
        "reading",
        "energy_meter_id",
    )
    # list_filter = (
    #    "tariff_register",
    #    # "energy_meter",
    # )
    inlines = [EnergyReadingCommentInline]
    save_as = True
    save_as_continue = True
    list_per_page = 10
    actions = [delete_item_without_confirm]
    raw_id_fields = ("energy_meter",)


class MeteringPointAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "dp_count",
        "name",
        "energy_meters",
        "energy_data",
        "is_sub_meter",
        "energy_meters",
        "utility",
        "location",
        "mp_categories",
        "comment",
    )

    def energy_data(self, obj):
        interv = CalculatedMeteringPointEnergyDeltaInterval.objects.first()
        if interv is None:
            return ""

        link = f'<a href="/ems/data/mp/{obj.pk}/{interv.pk}" \
            target="_blank">View Data</a><br>'
        # link += f'<a href="/pyscada_admin/ems/energyreading/?metering_point__id_exact={obj.pk}" target="_blank">Energy Readings</a>'  # noqa: E501 FIXME add reverse lockup for the URL

        return mark_safe(link)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            higher_level_metering_points_count=Count("higher_level_metering_points")
        )
        return qs

    @admin.display(ordering="higher_level_metering_points_count")
    def is_sub_meter(self, instance):
        return instance.higher_level_metering_points_count > 0

    is_sub_meter.boolean = True

    @admin.display
    def energy_meters(self, instance):
        return ", ".join(
            list(instance.energymeter_set.all().values_list("id_ext", flat=True))
        )

    @admin.display
    def mp_categories(self, instance):
        return ", ".join(list(instance.categories.all().values_list("name", flat=True)))

    def dp_count(self, instance):
        return instance.dp_count()

    try:
        for attribute_key in AttributeKey.objects.filter(
            show_in_meteringpoint_admin=True
        ):

            @admin.display(
                description=attribute_key.name,
                ordering=get_meteringpoint_ordering_by_attribute_key(attribute_key.pk),
            )
            def get_attribute_key(instance, key_name=attribute_key.name):
                return instance.meteringpointattribute_set.filter(
                    key__name=key_name
                ).first()

            list_display += (get_attribute_key,)
    except Exception:
        logger.warning(traceback.format_exc())

    list_display_links = ("id", "name")
    list_editable = ("comment",)
    filter_horizontal = ("higher_level_metering_points", "categories")

    list_filter = [
        "utility",
        (
            ("categories", ExclusiveMultiSelectRelatedFieldListFilter)
            if ExclusiveMultiSelectRelatedFieldListFilter is not None
            else "categories"
        ),
        IsSubMeterFilter,
        "location",
        "energy_price",
    ]

    search_fields = [
        "name",
        "comment",
    ]
    save_as = True
    save_as_continue = True
    inlines = [
        EnergyMeterInline,
        MeteringPointAttributeInline,
        MeteringPointAttachmentInline,
    ]
    actions = [update_calculated_energy_deltas, import_data_from_data_source]


class VirtualMeteringPointAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "energy_data",
        "utility",
        "mp_categories",
        "group",
        "comment",
    )
    list_display_links = ("id", "name")
    list_editable = ("comment",)
    list_filter = [
        "utility",
        (
            ("categories", ExclusiveMultiSelectRelatedFieldListFilter)
            if ExclusiveMultiSelectRelatedFieldListFilter is not None
            else "categories"
        ),
        "group",
    ]
    filter_horizontal = ("categories",)

    search_fields = [
        "name",
        "comment",
    ]
    save_as = True
    save_as_continue = True
    inlines = [
        VirtualMeteringPointAttributeInline,
        VirtualMeteringPointAttachmentInline,
    ]
    actions = [update_calculated_energy_deltas]

    def energy_data(self, obj):
        interv = CalculatedMeteringPointEnergyDeltaInterval.objects.first()
        if interv is None:
            return ""
        link = f'<a href="/ems/data/vmp/{obj.pk}/{interv.pk}" \
        target="_blank">View Data</a>'

        return mark_safe(link)

    @admin.display
    def mp_categories(self, instance):
        return ", ".join(list(instance.categories.all().values_list("name", flat=True)))

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        if obj is None:
            return form
        variable_list = "MeteringPoints:</br>"
        for id in obj.get_mp_ids_from_calculation():
            mp = MeteringPoint.objects.filter(pk=int(id)).first()
            if mp:
                variable_list += f"{id}: {str(mp)}</br>"
        variable_list += "VirtualMeteringPoints:</br>"
        for id in obj.get_vmp_ids_from_calculation():
            vmp = VirtualMeteringPoint.objects.filter(pk=int(id)).first()
            if vmp:
                variable_list += f"{id}: {str(vmp)}</br>"
        base_help_text = form.base_fields["calculation"].help_text

        form.base_fields["calculation"].help_text = (
            f"Used Variables:</br>{variable_list}</br>{base_help_text}"
        )
        return form


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
    # filter_horizontal = ('short_name','number', 'name', 'contruction_date',
    #                      'category__name', 'site', 'address__street',
    #                      'address__zip', 'address__town')
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

    def has_module_permission(self, request):
        return False


class BuildingInfoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "periode_from",
        "periode_to",
        "cost_unit",
        "owner",
    )
    list_display_links = ("id", "cost_unit")
    # list_editable = ()
    # filter_horizontal = ()
    save_as = True
    save_as_continue = True

    def has_module_permission(self, request):
        return False


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

    def has_module_permission(self, request):
        return False


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

    def has_module_permission(self, request):
        return False


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

    def has_module_permission(self, request):
        return False


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

    def has_module_permission(self, request):
        return False


class DataEntryFormAdmin(admin.ModelAdmin):
    inlines = [DataEntryFormElementInline]


class CalculationUnitAreaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
    )
    inlines = [CalculationUnitAreaPartInline, CalculationUnitAreaAttributeInline]


class CalculationUnitAreaPeriodAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "valid_from")

    inlines = []

    def has_module_permission(self, request):
        return False


class CalculatedMeteringPointEnergyDeltaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "interval",
        "reading_date",
        "energy_delta",
        "metering_point",
    )
    list_filter = ["interval", "metering_point"]


class CalculatedVirtualMeteringPointEnergyDeltaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "interval",
        "reading_date",
        "energy_delta",
        "virtual_metering_point",
    )
    list_filter = ["interval", "virtual_metering_point"]


class WeatherAdjustmentAdmin(admin.ModelAdmin):
    inlines = [WeatherAdjustmentPeriodInline]


class EnergyPriceAdmin(admin.ModelAdmin):
    inlines = [EnergyPricePeriodInline]


class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "label",
        "category",
        "datetime_changed",
        "datetime_added",
        "attached_file",
    )
    list_display_links = [
        "id",
        "label",
    ]
    list_filter = ["category", "groups"]
    filter_horizontal = ("groups",)


class AttachmentCategoryAdmin(admin.ModelAdmin):
    pass


class AttachmentGroupAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class EnergyPricePeriodAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class MeteringPointLocationAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class CalculationUnitAreaAttributeAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class CalculationUnitAreaPartAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class AttributeKeyAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class FloatAttributeKeyAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class MeteringPointAttachmentAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class VirtualMeteringPointAttachmentAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class EnergyMeterAttachmentAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class EnergyReadingTariffRegisterAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class MeteringPointCategoryAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return False


class DataExportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "label",
        "file_format",
        "periode_from",
        "periode_to",
        "interval",
        "download",
    )
    list_display_links = [
        "id",
        "label",
    ]
    list_filter = ("interval", "file_format", "include_cost", "include_coverage")
    filter_horizontal = (
        "metering_points",
        "virtual_metering_points",
        "categories",
        "attribute_keys",
    )
    actions = [download_data]
    save_as = True
    save_as_continue = True

    def download(self, obj):
        return mark_safe(f'<a href="/ems/data_export/{obj.pk}">Download</a>')


class DataImportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "label",
        "file_format",
        "upload",
        "last_import",
    )
    list_display_links = [
        "id",
        "label",
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "label",
                    "file_format",
                    "source_timezone",
                    "energy_meter",
                    "last_import",
                ]
            },
        ),
        (
            "CSV",
            {
                "classes": ["collapse"],
                "fields": [
                    "csv_skiprows",
                    "csv_time_col_nb",
                    "csv_time_col_format",
                    "csv_value_col_nb",
                    "csv_value_format",
                    "csv_value_scaling_factor",
                    "csv_delimiter",
                    "csv_decimal_separator",
                ],
            },
        ),
    ]
    readonly_fields = ["last_import"]
    save_as = True
    save_as_continue = True

    def get_queryset(self, request):
        # Store the request in the admin instance for later use
        self.request = request
        # Always call the parent class's get_queryset to maintain default behavior
        queryset = super().get_queryset(request)
        return queryset

    def upload(self, obj):
        """
        template = Template(
            f'<form enctype="multipart/form-data" method="post" action="/ems/data_import/{obj.pk}">'  # noqa: E501
            + '{% csrf_token %}><input type="file" name="file"><input type="submit" value="Upload File"></form>'  # noqa: E501
        )
        """
        html = ""
        html += (
            f'<div id="importfile_{obj.pk}" style="text-align: right; width: 100%;">'
        )
        html += f'<input type="file" name="file" id="file_{obj.pk}">'
        html += "{% csrf_token %}"
        html += '<button type="submit" class="input_submit" style="margin-right: 15px;"'
        html += 'onClick="(function(){'
        html += f"let csv_file = document.getElementById('file_{obj.pk}').files[0];"
        html += "let formData = new FormData();"
        html += "document.getElementById('changelist-form').enctype = 'multipart/form-data';"  # noqa: E501
        html += f"document.getElementById('changelist-form').action = '/ems/data_import/{obj.pk}';"  # noqa: E501
        html += "formData.append('file', csv_file);"
        html += "let csrfmiddlewaretoken = document.getElementsByName('csrfmiddlewaretoken')[0].value;"  # noqa: E501
        html += "formData.append('csrfmiddlewaretoken', csrfmiddlewaretoken);"
        html += f"fetch('/ems/data_import/{obj.pk}',"
        html += "{method: 'POST', body: formData, headers: { 'Content-Type': 'multipart/form-data'}});})()"  # noqa: E501
        html += '">Import File</button></div>'

        template = Template(html)

        context = RequestContext(self.request)
        return mark_safe(template.render(context))


class VariableDataSourceAdmin(admin.ModelAdmin):
    raw_id_fields = ("variable",)


admin_site.register(EnergyMeter, EnergyMeterAdmin)
admin_site.register(VariableDataSource, VariableDataSourceAdmin)
admin_site.register(MeteringPoint, MeteringPointAdmin)
admin_site.register(Address, AddressAdmin)
admin_site.register(BuildingInfo, BuildingInfoAdmin)
admin_site.register(BuildingCategory, BuildingCategoryAdmin)
admin_site.register(Building, BuildingAdmin)
admin_site.register(MeteringPointLocation, MeteringPointLocationAdmin)
admin_site.register(EnergyReading, EnergyReadingAdmin)
admin_site.register(EnergyReadingTariffRegister, EnergyReadingTariffRegisterAdmin)
admin_site.register(MeteringPointCategory, MeteringPointCategoryAdmin)

admin_site.register(Utility, UtilityAdmin)

admin_site.register(EnergyPrice, EnergyPriceAdmin)
admin_site.register(EnergyPricePeriod, EnergyPricePeriodAdmin)

admin_site.register(Attachment, AttachmentAdmin)
admin_site.register(AttachmentCategory, AttachmentCategoryAdmin)
admin_site.register(AttachmentGroup, AttachmentGroupAdmin)

admin_site.register(CalculationUnitArea, CalculationUnitAreaAdmin)
admin_site.register(CalculationUnitAreaAttribute, CalculationUnitAreaAttributeAdmin)
admin_site.register(CalculationUnitAreaPeriod, CalculationUnitAreaPeriodAdmin)
admin_site.register(CalculationUnitAreaPart, CalculationUnitAreaPartAdmin)

admin_site.register(WeatherAdjustment, WeatherAdjustmentAdmin)

admin_site.register(MeteringPointAttachment, MeteringPointAttachmentAdmin)
admin_site.register(VirtualMeteringPointAttachment, VirtualMeteringPointAttachmentAdmin)
admin_site.register(EnergyMeterAttachment, EnergyMeterAttachmentAdmin)

admin_site.register(AttributeKey, AttributeKeyAdmin)
admin_site.register(FloatAttributeKey, FloatAttributeKeyAdmin)

admin_site.register(VirtualMeteringPoint, VirtualMeteringPointAdmin)
admin_site.register(VirtualMeteringPointCategory, VirtualMeteringPointCategoryAdmin)
admin_site.register(VirtualMeteringPointGroup, VirtualMeteringPointGroupAdmin)

admin_site.register(
    CalculatedMeteringPointEnergyDelta, CalculatedMeteringPointEnergyDeltaAdmin
)
admin_site.register(
    CalculatedVirtualMeteringPointEnergyDelta,
    CalculatedVirtualMeteringPointEnergyDeltaAdmin,
)
admin_site.register(CalculatedMeteringPointEnergyDeltaInterval)

admin_site.register(DataEntryForm, DataEntryFormAdmin)
admin_site.register(DataExport, DataExportAdmin)
admin_site.register(DataImport, DataImportAdmin)
