# -*- coding: utf-8 -*-
from __future__ import unicode_literals

try:
    driver_ok = True
except ImportError:
    driver_ok = False

import logging

from pyscada.ems.models import MeteringPoint, VirtualMeteringPoint
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
        self.mp_to_calculate = [mp for mp in MeteringPoint.objects.all()] + [
            vmp for vmp in VirtualMeteringPoint.objects.all()
        ]
        self.dt_set = 0.1
        return True

    def loop(self):
        if len(self.mp_to_calculate) == 0:
            self.next_message = "done"
            return 0, None  # done

        mp = self.mp_to_calculate.pop(0)
        mp.update_calculated_energy_deltas()
        self.next_message = (
            f"Calculated {mp.name}, {len(self.mp_to_calculate)} to calulate"
        )

        return 1, None
