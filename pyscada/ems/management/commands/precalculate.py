#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json
from time import time

from django.core.management.base import BaseCommand

from pyscada.ems.models import MeteringPoint, VirtualMeteringPoint
from pyscada.models import BackgroundProcess


class Command(BaseCommand):
    help = "Run Maintenance Jobs for PyScada-EMS"

    def add_arguments(self, parser):
        parser.add_argument(
            "type", choices=["mp", "vmp", "all"], type=str, default="all"
        )
        parser.add_argument(
            "id",
            type=int,
            default=-1,
            nargs="?",
        )

    def handle(self, *args, **options):
        workers = 10
        if options["id"] >= 0:
            tic = time()
            if options["type"] == "all":
                print("argument id not supported for type == 'all'")

            if options["type"] == "mp":
                mp = MeteringPoint.objects.filter(pk=options["id"]).first()
                if mp is None:
                    print(f"MeteringPoint with id {options['id']} not found!")
                mp.update_calculated_energy_deltas()
                print(f"{(time()-tic):1.2f}")
                return

            if options["type"] == "vmp":
                tic = time()
                vmp = VirtualMeteringPoint.objects.filter(pk=options["id"]).first()
                if vmp is None:
                    print(f"VirtualMeteringPoint with id {options['id']} not found!")
                vmp.update_calculated_energy_deltas()
                print(f"{(time()-tic):1.2f}")
                return

        if options["type"] in ["mp", "all"] and options["id"] == -1:
            nb_mp = MeteringPoint.objects.count()
            mp_i = 1
            mp_ids_to_calculate = []
            for worker_id in range(workers):
                mp_ids_to_calculate.append([])
            worker = 0
            for mp in MeteringPoint.objects.all():

                print(f"add mp {mp_i}/{nb_mp}: {mp.name} ", end="", flush=True)
                # mp.update_calculated_energy_deltas()
                mp_ids_to_calculate[worker % workers].append(mp.pk)
                worker += 1
                mp_i += 1
                print(" done")

            for worker_id in range(workers):
                process_class_kwargs = json.dumps(
                    {"mp_ids_to_calculate": mp_ids_to_calculate[worker_id]}
                )
                if len(process_class_kwargs) > 400:
                    print(
                        f"process_class_kwargs to long \
                                ({len(process_class_kwargs)}>400)"
                    )
                    continue

                bp = BackgroundProcess(
                    pid=0,
                    label="update precalculated mp",
                    enabled=True,
                    parent_process_id=1,
                    process_class="pyscada.ems.daemon.PreCalculationBackgroundTask",
                    process_class_kwargs=process_class_kwargs,
                )
                bp.save()

        if options["type"] in ["vmp", "all"] and options["id"] == -1:
            process_class_kwargs = json.dumps({"vmp_ids_to_calculate": "all"})
            bp = BackgroundProcess(
                pid=0,
                label="update precalculated vmp",
                enabled=True,
                parent_process_id=1,
                process_class="pyscada.ems.daemon.PreCalculationBackgroundTask",
                process_class_kwargs=process_class_kwargs,
            )
            bp.save()
