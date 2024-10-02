#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.core.management.base import BaseCommand

from pyscada.ems.models import MeteringPoint, VirtualMeteringPoint


class Command(BaseCommand):
    help = "Run Maintenance Jobs for PyScada-EMS"

    def add_arguments(self, parser):
        parser.add_argument(
            "type", choices=["mp", "vmp", "all"], type=str, default="all"
        )

    def handle(self, *args, **options):
        if options["type"] in ["mp", "all"]:
            nb_mp = MeteringPoint.objects.count()
            mp_i = 1
            for mp in MeteringPoint.objects.all():
                print(f"mp {mp_i}/{nb_mp}: {mp.name} ", end="", flush=True)
                mp.update_calculated_energy_deltas()
                mp_i += 1
                print(" done")

        if options["type"] in ["vmp", "all"]:
            nb_mp = VirtualMeteringPoint.objects.count()
            mp_i = 1
            for mp in VirtualMeteringPoint.objects.all():
                print(f"vmp {mp_i}/{nb_mp}: {mp.name} ", end="", flush=True)
                mp.update_calculated_energy_deltas()
                mp_i += 1
                print(" done")
