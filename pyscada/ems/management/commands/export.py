#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export Data from the PyScada-EMS"

    def add_arguments(self, parser):
        parser.add_argument(
            "template",
            type=int,
        )

    def handle(self, *args, **options):
        raise NotImplementedError
