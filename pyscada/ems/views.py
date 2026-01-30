# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from datetime import datetime
from uuid import uuid4

import pytz
from django.conf import settings
from django.http import Http404, HttpResponse
from django.template.response import TemplateResponse

from pyscada.core import version as core_version
from pyscada.ems.models import (
    CalculatedMeteringPointEnergyDelta,
    CalculatedMeteringPointEnergyDeltaInterval,
    CalculatedVirtualMeteringPointEnergyDelta,
    DataEntryForm,
    DataExport,
    MeteringPoint,
    VirtualMeteringPoint,
    calculate_start_datetime,
    calculate_timestamps,
)
from pyscada.hmi.views import login_required

logger = logging.getLogger(__name__)


@login_required
def ems_view(request):
    base_template = "base.html"
    form_template = "ems_form.html"
    add_context = {}

    javascript_files_list = []
    css_files_list = []

    context = {
        "base_html": base_template,
        "include": [],
        "form": {
            "title": "this is the Title",
            "web_id": 100,  # should be set later from the Model
            "uuid": uuid4(),
        },
        "user": request.user,
        "version_string": core_version,
        "link_target": (
            settings.LINK_TARGET if hasattr(settings, "LINK_TARGET") else "_blank"
        ),
        "javascript_files_list": javascript_files_list,
        "css_files_list": css_files_list,
    }

    context.update(add_context)

    return TemplateResponse(request, form_template, context)


@login_required
def form_add_data(request, form_id):
    base_template = "base.html"
    form_template = "ems_form.html"
    add_context = {}

    javascript_files_list = []
    css_files_list = []
    try:
        form_data = DataEntryForm.objects.get(pk=form_id)
    except DataEntryForm.DoesNotExist:
        raise Http404("DataEntryForm does not exist")

    context = {
        "base_html": base_template,
        "include": [],
        "form": form_data,
        "user": request.user,
        "uuid": uuid4(),
        "version_string": core_version,
        "link_target": (
            settings.LINK_TARGET if hasattr(settings, "LINK_TARGET") else "_blank"
        ),
        "javascript_files_list": javascript_files_list,
        "css_files_list": css_files_list,
    }

    context.update(add_context)

    return TemplateResponse(request, form_template, context)


@login_required
def form_add_data_submit(request, form_id):
    base_template = "base.html"
    form_template = "ems_form_submit.html"
    add_context = {}

    javascript_files_list = []
    css_files_list = []
    try:
        form_data = DataEntryForm.objects.get(pk=form_id)
    except DataEntryForm.DoesNotExist:
        raise Http404("DataEntryForm does not exist")

    request.POST

    context = {
        "base_html": base_template,
        "include": [],
        "form": form_data,
        "user": request.user,
        "uuid": uuid4(),
        "version_string": core_version,
        "link_target": (
            settings.LINK_TARGET if hasattr(settings, "LINK_TARGET") else "_blank"
        ),
        "javascript_files_list": javascript_files_list,
        "css_files_list": css_files_list,
    }

    context.update(add_context)

    return TemplateResponse(request, form_template, context)


@login_required
def data_export(request, data_export_id):
    try:
        dx = DataExport.objects.get(pk=data_export_id)
    except DataExport.DoesNotExist:
        raise Http404("DataExport does not exist")

    buffer = dx.make_buffer()

    if dx.file_format == "csv":
        content_type = "application/csv"
    elif dx.file_format == "xlsx":
        content_type = "application/xlsx"
    elif dx.file_format == "json":
        content_type = "application/json"
    else:
        raise Http404("DataExport export format not supported")

    return HttpResponse(
        buffer.getvalue(),
        headers={
            "Content-Type": content_type,
            "Content-Disposition": 'attachment; filename="%s"' % dx.full_filename,
        },
    )


@login_required
def energy_data_export_xls(request, meteringpoint_ids):
    raise Http404("DataEntryForm does not exist")


def energy_data_view(request, dx, mp, interval):
    base_template = "base.html"

    javascript_files_list = []
    css_files_list = []

    # display the data in columns where every year represents the data
    # of one year, so that same day, month or year data is displayed in
    # on row for beter compairability

    # first pass: reorder data by year (in the target timezone)
    cols = {}
    for item in dx.all():
        year = (
            (item.reading_date - interval.get_interval_relativedelta())
            .astimezone(pytz.timezone(interval.timezone))
            .year
        )
        if year not in cols:
            cols[year] = {}
        cols[year][item.reading_date.timestamp()] = item

    # second pass: get the number of rows nessesary to display the data
    row_nb_max = 0
    for col in cols.keys():
        row_nb_max = max(row_nb_max, len(cols[col]))

    # third pass: reorder the data into rows
    rows = {}
    for col in cols.keys():
        start_datetime = calculate_start_datetime(
            datetime(col, 1, 1, 0, 0, tzinfo=pytz.timezone(interval.timezone)), interval
        )
        end_datetime = datetime(
            col, 12, 31, 23, 59, 59, tzinfo=pytz.timezone(interval.timezone)
        )
        timestamps = calculate_timestamps(start_datetime, end_datetime, interval)
        for timestamp in timestamps:
            if interval.get_interval_length() == "week":
                row_key = "Week " + (
                    datetime.fromtimestamp(timestamp)
                    - interval.get_interval_relativedelta()
                ).strftime(
                    "%W"
                )  # FIXME add decision for the first day of the week based on local
            else:
                row_key = (
                    (
                        datetime.fromtimestamp(timestamp)
                        - interval.get_interval_relativedelta()
                    ).strftime("%m.%d %H:%M")
                    + " - "
                    + datetime.fromtimestamp(timestamp).strftime("%m.%d %H:%M")
                )
            if row_key not in rows:
                rows[row_key] = {}
                for row_col in cols.keys():
                    rows[row_key][row_col] = None

            if timestamp in cols[col]:
                rows[row_key][col] = cols[col][timestamp]
    # sort by Key to bring dates () in the right order
    rows = dict(sorted(rows.items()))
    links = []

    for item in CalculatedMeteringPointEnergyDeltaInterval.objects.all():
        link = {}
        link["active"] = ""
        if item.pk == interval.pk:
            link["active"] = "class=active"

        if type(mp) is MeteringPoint:
            link["url"] = f"/ems/data/mp/{mp.pk}/{item.pk}"
        else:
            link["url"] = f"/ems/data/vmp/{mp.pk}/{item.pk}"
        link["text"] = f"Data {str(item)}"
        links.append(link)

    context = {
        "base_html": base_template,
        "include": [],
        "date_type": "(m.d H:M)" if interval.get_interval_length() != "week" else "",
        "meteringpoint_type": (
            "Meteringpoint" if type(mp) is MeteringPoint else "VirtualMeteringpoint"
        ),
        "point_count": dx.count(),
        "utility": str(mp.utility),
        "categories": ", ".join([str(item) for item in mp.categories.all()]),
        "rows": rows,
        "col_headers": list(cols.keys()),
        "mp": mp,
        "links": links,
        "unit": mp.unit.unit if mp.unit is not None else "-",
        "interval": interval,
        "last_update": (
            "Outdated"
            if mp.last_precalculation_update is None
            else mp.last_precalculation_update
        ),
        "user": request.user,
        "version_string": core_version,
        "javascript_files_list": javascript_files_list,
        "css_files_list": css_files_list,
    }

    return context


@login_required
def energy_data_mp_view(request, meteringpoint_id, interval_id):
    form_template = "energy_data_view.html"

    try:
        dx = CalculatedMeteringPointEnergyDelta.objects.filter(
            metering_point_id=meteringpoint_id, interval_id=interval_id
        )
        mp = MeteringPoint.objects.get(pk=meteringpoint_id)
        interval = CalculatedMeteringPointEnergyDeltaInterval.objects.get(
            pk=interval_id
        )

    except MeteringPoint.DoesNotExist:
        raise Http404("MeteringPoint does not exist")
    except CalculatedMeteringPointEnergyDeltaInterval.DoesNotExist:
        raise Http404("CalculatedMeteringPointEnergyDeltaInterval does not exist")

    context = energy_data_view(request, dx, mp, interval)

    return TemplateResponse(request, form_template, context)


@login_required
def energy_data_vmp_view(request, virtualmeteringpoint_id, interval_id):
    form_template = "energy_data_view.html"

    try:
        dx = CalculatedVirtualMeteringPointEnergyDelta.objects.filter(
            virtual_metering_point_id=virtualmeteringpoint_id, interval_id=interval_id
        )
        vmp = VirtualMeteringPoint.objects.get(pk=virtualmeteringpoint_id)
        interval = CalculatedMeteringPointEnergyDeltaInterval.objects.get(
            pk=interval_id
        )

    except VirtualMeteringPoint.DoesNotExist:
        raise Http404("VirtualMeteringPoint does not exist")
    except CalculatedMeteringPointEnergyDeltaInterval.DoesNotExist:
        raise Http404("CalculatedMeteringPointEnergyDeltaInterval does not exist")

    context = energy_data_view(request, dx, vmp, interval)
    return TemplateResponse(request, form_template, context)


@login_required
def metering_point_view(request, category=None):
    base_template = "base.html"
    form_template = "metering_point_view.html"
    add_context = {}

    javascript_files_list = []
    css_files_list = []
    attr_column_header = []
    data = []

    for mp in MeteringPoint.objects.all():
        for key_name in mp.meteringpointattribute_set.values_list(
            "key__name", flat=True
        ):
            if key_name not in attr_column_header:
                attr_column_header.append(key_name)

    for mp in MeteringPoint.objects.all():
        row_data = {}
        row_data["id"] = mp.id
        row_data["name"] = mp.name
        row_data["utility"] = mp.utility.name
        row_data["unit"] = "-" if mp.unit is None else mp.unit.unit
        row_data["location"] = (
            "-"
            if mp.location is None
            else f"{mp.location.building.short_name} {mp.location.room}"
        )
        row_data["comment"] = mp.comment
        row_data["in_operation_from"] = (
            "-" if mp.in_operation_from is None else mp.in_operation_from.isoformat()
        )
        row_data["in_operation_to"] = (
            "-" if mp.in_operation_to is None else mp.in_operation_to.isoformat()
        )
        row_data["categories"] = ", ".join(mp.categories.values_list("name", flat=True))
        row_data["energymeter_ids"] = ", ".join(
            mp.energymeter_set.values_list("id_ext", flat=True)
        )
        for key_name in attr_column_header:
            row_data[key_name] = mp.meteringpointattribute_set.filter(
                key__name=key_name
            ).first()
            if row_data[key_name] is None:
                row_data[key_name] = "-"
        data.append(row_data)

    context = {
        "base_html": base_template,
        "include": [],
        "data": data,
        "header_columns": list(data[0].keys()),
        "user": request.user,
        "version_string": core_version,
        "javascript_files_list": javascript_files_list,
        "css_files_list": css_files_list,
    }

    context.update(add_context)

    return TemplateResponse(request, form_template, context)
