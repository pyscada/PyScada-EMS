# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.urls import path

from pyscada.ems import views as ems_views

urlpatterns = [
    path("ems/form/add_data/<int:form_id>", ems_views.form_add_data),
    path("ems/form/add_data/submit/<int:form_id>", ems_views.form_add_data_submit),
    path("ems/data_export/<int:data_export_id>", ems_views.data_export),
    path("ems/data_import/<int:data_import_id>", ems_views.data_import),
    path("ems/form/", ems_views.ems_view),
    path(
        "ems/data/mp/<int:meteringpoint_id>/<int:interval_id>",
        ems_views.energy_data_mp_view,
    ),
    path(
        "ems/data/vmp/<int:virtualmeteringpoint_id>/<int:interval_id>",
        ems_views.energy_data_vmp_view,
    ),
    path("ems/data/metering_points/", ems_views.metering_point_view),
]
