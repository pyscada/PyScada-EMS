from datetime import datetime

from django.test import TestCase

from pyscada.ems.models import caluculate_timestamps


# Create your tests here.
class CaluculateTimestampsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start_date = datetime.strptime(
            "01-01-2022 00:00:00+01:00", "%d-%m-%Y %H:%M:%S%z"
        )
        cls.end_date = datetime.strptime(
            "30-03-2022 00:00:00+01:00", "%d-%m-%Y %H:%M:%S%z"
        )

    def test_defaults(self):
        result = caluculate_timestamps(
            start_datetime=self.start_date, end_datetime=self.end_date
        )
        self.assertEqual(result[0], self.start_date.timestamp())
        self.assertEqual(result[-1], self.end_date.timestamp())
