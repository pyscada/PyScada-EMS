# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from uuid import uuid4

from django.conf import settings
from django.http import Http404
from django.template.response import TemplateResponse
from django.views.decorators.csrf import requires_csrf_token

from pyscada.core import version as core_version
from pyscada.ems.models import DataEntryForm
from pyscada.hmi.views import unauthenticated_redirect

logger = logging.getLogger(__name__)


@unauthenticated_redirect
@requires_csrf_token
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


@unauthenticated_redirect
@requires_csrf_token
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


@unauthenticated_redirect
@requires_csrf_token
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
