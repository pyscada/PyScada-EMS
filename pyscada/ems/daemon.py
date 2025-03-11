# -*- coding: utf-8 -*-
from __future__ import unicode_literals

try:
    driver_ok = True
except ImportError:
    driver_ok = False

import logging

from pyscada.ems.models import MeteringPoint, VirtualMeteringPoint
from pyscada.models import BackgroundProcess
from pyscada.utils.scheduler import Process

logger = logging.getLogger(__name__)


class Device:
    """
    EMS Background class
    """

    def __init__(self, device):
        self.device = device
        self._device_not_accessible = 0
        self.variables = {}

    def request_data(self):
        """process the data that was added to pyscada db"""
        output = []
        return output


class PreCalculationBackgroundTask(Process):

    def init_process(self):
        if hasattr(self, "mp_ids_to_calculate") or hasattr(
            self, "vmp_ids_to_calculate"
        ):
            self.mp_to_calculate = []
        else:
            self.mp_to_calculate = [mp for mp in MeteringPoint.objects.all()]
            self.calculate_type = "mp"

        if hasattr(self, "mp_ids_to_calculate"):
            self.calculate_type = "mp"
            if self.mp_ids_to_calculate == "all":
                self.mp_to_calculate += [mp for mp in MeteringPoint.objects.all()]
            elif self.mp_ids_to_calculate == "none":
                pass
            else:
                self.mp_to_calculate += [
                    mp
                    for mp in MeteringPoint.objects.filter(
                        pk__in=self.mp_ids_to_calculate
                    )
                ]

        elif hasattr(self, "vmp_ids_to_calculate"):
            self.calculate_type = "vmp"
            if self.vmp_ids_to_calculate == "all":
                self.mp_to_calculate += [
                    mp for mp in VirtualMeteringPoint.objects.all()
                ]
            elif self.vmp_ids_to_calculate == "none":
                pass
            else:
                self.mp_to_calculate += [
                    mp
                    for mp in VirtualMeteringPoint.objects.filter(
                        pk__in=self.vmp_ids_to_calculate
                    )
                ]

        self.dt_set = 0.1
        return True

    def loop(self):
        if len(self.mp_to_calculate) == 0:
            self.next_message = "done"
            return 0, None  # done

        if self.calculate_type == "vmp" and BackgroundProcess.objects.filter(
            process_class="pyscada.ems.daemon.PreCalculationBackgroundTask",
            label="update precalculated mp",
            done=False,
        ):
            self.dt_set = 30
            self.next_message = "wait for running update mp processes to finish"
            return 1, None

        mp = self.mp_to_calculate.pop(0)
        self.dt_set = 0.1
        mp.update_calculated_energy_deltas()
        self.next_message = (
            f"Calculated {mp.name}, {len(self.mp_to_calculate)} to calulate"
        )

        return 1, None
