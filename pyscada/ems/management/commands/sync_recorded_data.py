#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from datetime import datetime

##
import pytz
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from pyscada.ems.models import EnergyMeter, EnergyReading
from pyscada.models import Variable

dry_run = False


def factor_from_unit(unit):
    if unit == "kWh":
        return 1.0

    if unit == "MWh":
        return 1000.0

    if unit == "Wh":
        return 1.0 / 1000.0

    return 0.0


class Command(BaseCommand):
    help = "Sync Recorded Data from PyScada to PyScada-EMS"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        date_to = datetime.now()
        meter_updated = []
        er_data = []
        if dry_run:
            print(
                "!!!!!!!!!!!!!!!!!!!! Dry Run !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )

        for meter in EnergyMeter.objects.all():
            close_old_connections()
            if meter.data_source_variable is None:
                continue

            date_from = meter.get_last_datetime(
                datetime(2016, 1, 1, 0, 0, tzinfo=pytz.utc)
            )
            close_old_connections()
            data = Variable.objects.read_multiple(
                variable_ids=[meter.data_source_variable.variable_id],
                time_min=date_from.timestamp(),
                time_max=date_to.timestamp(),
                query_first_value=True,
            )
            data = data[meter.data_source_variable.variable_id]
            factor = factor_from_unit(meter.data_source_variable.variable.unit.unit)
            last_reading = meter.energyreading_set.last()
            old_reading = None
            if last_reading:
                old_reading = float(last_reading.reading)
            plausible = True
            print(f"{meter}")

            for i in range(len(data)):
                close_old_connections()
                # read the Unit of the Data from the current Line and convert it to a
                # factor for kWh conversion
                reading_date = datetime.fromtimestamp(data[i][0] / 1000).replace(
                    tzinfo=pytz.timezone("CET")
                )
                reading = data[i][1] * factor
                # FIXME check if reading is plausible

                if meter.pk not in meter_updated:
                    to_delete = meter.energyreading_set.filter(
                        reading_date__gte=reading_date
                    ).count()
                    if to_delete > 0:
                        print(f"deleted old readings {meter.pk}: {meter} {to_delete}")
                        if not dry_run:
                            meter.energyreading_set.filter(
                                reading_date__gte=reading_date
                            ).delete()

                    meter_updated.append(meter.pk)

                if i == 0:
                    print(f"First {reading_date.isoformat()[:19]} {reading}")
                    if old_reading is None:
                        old_reading = reading

                if i == (len(data) - 1):
                    print(f"Last {reading_date.isoformat()[:19]} {reading}")
                """
                if meter.meter_type == "upcounting":
                    #if round(reading, 6) < old_reading:
                    #    #plausible = False
                    #    print(f"{reading_date.isoformat()[:19]} \
                    #    {reading} < {old_reading} is not plausible")
                    #    continue
                """
                old_reading = round(reading, 6)

                er = EnergyReading(
                    reading_date=reading_date, reading=reading, energy_meter=meter
                )
                er_data.append(er)
            print("loop done")
            if dry_run:
                print(f"would have added {len(er_data)} new readings")
            if not dry_run and plausible:
                close_old_connections()
                max_add = 1000
                for i in range(0, len(er_data), max_add):
                    EnergyReading.objects.bulk_create(
                        er_data[i : min(len(er_data) - 1, i + max_add)]
                    )
                    print(
                        f"added new readings: \
                         {min((i+max_add), len(er_data))/len(er_data)*100}"
                    )
                print(f"added new readings: {len(er_data)}")

            er_data = []
