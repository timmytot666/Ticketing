import unittest
from datetime import datetime, date, time, timedelta, timezone
import sys
import os

# Adjust path to import from parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sla_calculator import calculate_due_date # The function to test

class TestSLACalculator(unittest.TestCase):

    def setUp(self):
        self.sample_business_schedule = {
            "monday": (time(9, 0), time(17, 0)),
            "tuesday": (time(9, 0), time(17, 0)),
            "wednesday": (time(9, 0), time(17, 0)),
            "thursday": (time(9, 0), time(17, 0)),
            "friday": (time(9, 0), time(17, 0)),
            "saturday": None,
            "sunday": None
        }
        self.sample_public_holidays = [
            date(2024, 1, 1),  # New Year's Day (Monday)
            date(2024, 5, 27), # Memorial Day (Monday)
        ]
        # Tolerance for comparing datetimes (in seconds) due to potential float precision
        self.datetime_comparison_tolerance_seconds = 60


    def assertDateTimeAlmostEqual(self, dt1, dt2, delta_seconds=60, msg=None):
        """Asserts that two datetimes are within a certain tolerance."""
        if dt1 is None and dt2 is None: return
        if dt1 is None or dt2 is None:
            raise self.failureException(msg or f"One datetime is None, the other is not: {dt1} vs {dt2}")

        # Ensure both are offset-aware and in UTC for fair comparison if they come from different sources
        if dt1.tzinfo is None: dt1 = dt1.replace(tzinfo=timezone.utc)
        else: dt1 = dt1.astimezone(timezone.utc)

        if dt2.tzinfo is None: dt2 = dt2.replace(tzinfo=timezone.utc)
        else: dt2 = dt2.astimezone(timezone.utc)

        self.assertAlmostEqual(dt1, dt2, delta=timedelta(seconds=delta_seconds), msg=msg)


    def test_within_same_business_day(self):
        start_dt = datetime(2023, 12, 28, 10, 0, 0, tzinfo=timezone.utc) # Thursday
        expected_dt = datetime(2023, 12, 28, 12, 0, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 2, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_to_end_of_business_day(self):
        start_dt = datetime(2023, 12, 28, 15, 0, 0, tzinfo=timezone.utc) # Thursday
        expected_dt = datetime(2023, 12, 28, 17, 0, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 2, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_span_overnight_to_next_business_day(self):
        start_dt = datetime(2023, 12, 28, 15, 0, 0, tzinfo=timezone.utc) # Thursday
        expected_dt = datetime(2023, 12, 29, 10, 0, 0, tzinfo=timezone.utc) # Friday
        calculated_dt = calculate_due_date(start_dt, 4, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_start_before_business_hours(self):
        start_dt = datetime(2023, 12, 28, 7, 0, 0, tzinfo=timezone.utc) # Thursday
        expected_dt = datetime(2023, 12, 28, 10, 0, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 1, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_start_after_business_hours(self):
        start_dt = datetime(2023, 12, 28, 18, 0, 0, tzinfo=timezone.utc) # Thursday
        expected_dt = datetime(2023, 12, 29, 10, 0, 0, tzinfo=timezone.utc) # Friday
        calculated_dt = calculate_due_date(start_dt, 1, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_span_weekend_friday_to_tuesday(self):
        # 2023-12-29 is Friday. 2024-01-01 (Mon) is holiday. So next business day is Tue 2024-01-02.
        start_dt = datetime(2023, 12, 29, 15, 0, 0, tzinfo=timezone.utc) # Friday
        # Add 3 business hours: 2h on Fri (15-17). 1h remaining.
        # Sat, Sun skipped. Mon (Jan 1) holiday.
        # Tue (Jan 2) starts 9am. 9am + 1h = 10am.
        expected_dt = datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 3, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_span_public_holiday_new_year(self):
        # 2023-12-29 is Friday. 2024-01-01 (Mon) is holiday.
        start_dt = datetime(2023, 12, 29, 16, 0, 0, tzinfo=timezone.utc) # Friday, 1h left in day
        # Add 2 business hours: 1h on Fri. 1h remaining.
        # Sat, Sun skipped. Mon (Jan 1) holiday.
        # Tue (Jan 2) starts 9am. 9am + 1h = 10am.
        expected_dt = datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 2, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_span_public_holiday_memorial_day(self):
        # 2024-05-24 is a Friday. 2024-05-27 (Mon) is Memorial Day holiday.
        start_dt = datetime(2024, 5, 24, 16, 0, 0, tzinfo=timezone.utc) # Friday, 1h left
        # Add 3 business hours: 1h on Fri. 2h remaining.
        # Sat, Sun skipped. Mon (May 27) holiday.
        # Tue (May 28) starts 9am. 9am + 2h = 11am.
        expected_dt = datetime(2024, 5, 28, 11, 0, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 3, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)


    def test_sla_of_zero_hours(self):
        start_dt = datetime(2023, 12, 28, 11, 0, 0, tzinfo=timezone.utc)
        expected_dt = start_dt
        calculated_dt = calculate_due_date(start_dt, 0, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_start_on_weekend_saturday(self):
        # 2023-12-30 is Saturday. 2024-01-01 (Mon) is holiday. Next business day is Tue 2024-01-02.
        start_dt = datetime(2023, 12, 30, 10, 0, 0, tzinfo=timezone.utc)
        # Add 2 business hours. Starts Tue 9am. 9am + 2h = 11am.
        expected_dt = datetime(2024, 1, 2, 11, 0, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 2, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_start_on_public_holiday_monday(self):
        # 2024-01-01 (Mon) is holiday. Next business day is Tue 2024-01-02.
        start_dt = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        # Add 3 business hours. Starts Tue 9am. 9am + 3h = 12pm.
        expected_dt = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 3, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_large_sla_40_business_hours(self):
        # Start on a Thursday, 2023-12-21. (2024-01-01 is Mon holiday)
        # Business week is 5 days * 8 hours/day = 40 hours.
        start_dt = datetime(2023, 12, 21, 10, 0, 0, tzinfo=timezone.utc) # Thursday 10am
        # Thu(21st): 10am-5pm = 7 hours. (33h rem)
        # Fri(22nd): 9am-5pm = 8 hours. (25h rem)
        # Sat(23rd), Sun(24th): Skip.
        # Mon(25th): 9am-5pm = 8 hours. (17h rem) (Assuming not a holiday for this test case)
        # Tue(26th): 9am-5pm = 8 hours. (9h rem)
        # Wed(27th): 9am-5pm = 8 hours. (1h rem)
        # Thu(28th): 9am + 1h = 10am.
        # This scenario does not use the sample_public_holidays to test a full week span.
        expected_dt = datetime(2023, 12, 28, 10, 0, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 40, self.sample_business_schedule, []) # No holidays for this one
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_start_at_exact_end_of_business_day(self):
        start_dt = datetime(2023, 12, 28, 17, 0, 0, tzinfo=timezone.utc) # Thursday EOD
        expected_dt = datetime(2023, 12, 29, 10, 0, 0, tzinfo=timezone.utc) # Friday 9am + 1h
        calculated_dt = calculate_due_date(start_dt, 1, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_start_at_exact_start_of_business_day_full_day_sla(self):
        start_dt = datetime(2023, 12, 28, 9, 0, 0, tzinfo=timezone.utc) # Thursday SOD
        expected_dt = datetime(2023, 12, 28, 17, 0, 0, tzinfo=timezone.utc) # Thursday EOD
        calculated_dt = calculate_due_date(start_dt, 8, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_fractional_hours(self):
        start_dt = datetime(2023, 12, 28, 10, 0, 0, tzinfo=timezone.utc) # Thursday
        expected_dt = datetime(2023, 12, 28, 12, 30, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 2.5, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_span_into_next_day_with_fractional_hours(self):
        start_dt = datetime(2023, 12, 28, 16, 30, 0, tzinfo=timezone.utc) # Thursday, 0.5h left
        # Add 1.0 hour: 0.5h on Thu. 0.5h remaining.
        # Fri starts 9am. 9am + 0.5h = 9:30am.
        expected_dt = datetime(2023, 12, 29, 9, 30, 0, tzinfo=timezone.utc)
        calculated_dt = calculate_due_date(start_dt, 1.0, self.sample_business_schedule, self.sample_public_holidays)
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_naive_start_time_assumes_utc(self):
        start_dt_naive = datetime(2023, 12, 28, 10, 0, 0)
        expected_dt = datetime(2023, 12, 28, 12, 0, 0, tzinfo=timezone.utc)
        with patch('builtins.print') as mock_print: # Suppress warning for this test
            calculated_dt = calculate_due_date(start_dt_naive, 2, self.sample_business_schedule, self.sample_public_holidays)
            mock_print.assert_any_call(unittest.mock.string_containing("Warning: Naive start_time_utc provided"))
        self.assertDateTimeAlmostEqual(calculated_dt, expected_dt, self.datetime_comparison_tolerance_seconds)

    def test_empty_business_schedule_hits_max_iterations(self):
        empty_schedule = {day: None for day in self.sample_business_schedule.keys()}
        start_dt = datetime(2023, 12, 28, 10, 0, 0, tzinfo=timezone.utc)
        # Expect a warning to be printed due to max iterations
        with patch('builtins.print') as mock_print:
            # The actual return time will be far in the future, determined by MAX_ITERATIONS * 1 day advances
            # We are mostly interested in the warning here.
            calculated_dt = calculate_due_date(start_dt, 8, empty_schedule, [])
            self.assertTrue(any("Warning: SLA calculation exceeded max iterations" in call_arg[0][0]
                                for call_arg in mock_print.call_args_list))


if __name__ == '__main__':
    unittest.main()
