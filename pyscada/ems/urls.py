# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.urls import path

from pyscada.ems import views as ems_views

urlpatterns = [
    path("ems/form/add_data/<int:form_id>", ems_views.form_add_data),
    path("ems/form/add_data/submit/<int:form_id>", ems_views.form_add_data_submit),
    path("ems/data_export/<int:data_export_id>", ems_views.data_export),
    path("ems/form/", ems_views.ems_view),
]
