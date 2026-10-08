import calendar
import datetime as dt
import pytest

from courier_runtime.deadlines import (
    add_months,
    deadline,
    easter,
    holidays_niedersachsen,
    next_working_day,
)

D = dt.date


class TestGermanDeadlinesExtended:
    """Rigorous edge-case coverage for administrative deadline calculations (Bescheide)."""

    def test_easter_across_multiple_years(self):
        # Known Easter Sunday dates verified against astronomical calendar
        known_easters = {
            2024: D(2024, 3, 31),
            2025: D(2025, 4, 20),
            2026: D(2026, 4, 5),
            2027: D(2027, 3, 28),
            2028: D(2028, 4, 16),
            2029: D(2029, 4, 1),
            2030: D(2030, 4, 21),
        }
        for year, expected in known_easters.items():
            assert easter(year) == expected, f"Failed easter calculation for year {year}"

    def test_holidays_niedersachsen_complete_set(self):
        for year in [2025, 2026, 2027, 2028]:
            holidays = holidays_niedersachsen(year)
            e = easter(year)
            # Must include fixed holidays:
            assert D(year, 1, 1) in holidays  # Neujahr
            assert D(year, 5, 1) in holidays  # Tag der Arbeit
            assert D(year, 10, 3) in holidays  # Tag der Deutschen Einheit
            assert D(year, 10, 31) in holidays  # Reformationstag
            assert D(year, 12, 25) in holidays  # 1. Weihnachtstag
            assert D(year, 12, 26) in holidays  # 2. Weihnachtstag
            # Must include easter-relative holidays:
            assert (e - dt.timedelta(days=2)) in holidays  # Karfreitag
            assert (e + dt.timedelta(days=1)) in holidays  # Ostermontag
            assert (e + dt.timedelta(days=39)) in holidays  # Christi Himmelfahrt
            assert (e + dt.timedelta(days=50)) in holidays  # Pfingstmontag
            assert len(holidays) == 10

    def test_next_working_day_weekend_and_holiday_rolling(self):
        # 2026-05-01 is Friday (Tag der Arbeit)
        # Saturday is 05-02, Sunday is 05-03 -> Next working day must be Monday 2026-05-04
        assert next_working_day(D(2026, 5, 1)) == D(2026, 5, 4)

        # 2026-10-03 is Saturday (Tag der Deutschen Einheit)
        # Sunday is 10-04 -> Next working day must be Monday 2026-10-05
        assert next_working_day(D(2026, 10, 3)) == D(2026, 10, 5)

        # Regular weekday (Tuesday) remains unchanged
        assert next_working_day(D(2026, 6, 9)) == D(2026, 6, 9)

    def test_add_months_leap_year_handling(self):
        # 2028 is a leap year (Feb 29 exists)
        assert add_months(D(2028, 1, 31), 1) == D(2028, 2, 29)
        # 2026 is non-leap (Feb 28)
        assert add_months(D(2026, 1, 31), 1) == D(2026, 2, 28)
        # Multi-month jump from Aug 31 to Feb (6 months) in leap year
        assert add_months(D(2027, 8, 31), 6) == D(2028, 2, 29)
        # Jump across year boundary: Nov 30 + 3 months -> Feb 28 (or 29)
        assert add_months(D(2025, 11, 30), 3) == D(2026, 2, 28)

    def test_deadline_fiction_days_variance(self):
        # Legacy 3-day fiction
        r3 = deadline(D(2026, 3, 1), fiction_days=3)
        assert r3["bekanntgabe"] == D(2026, 3, 4)
        assert r3["deadline"] == next_working_day(D(2026, 4, 4))

        # Modern 4-day fiction (default)
        r4 = deadline(D(2026, 3, 1), fiction_days=4)
        assert r4["bekanntgabe"] == D(2026, 3, 5)
        assert r4["deadline"] == next_working_day(D(2026, 4, 5))

    def test_deadline_custom_posted_on_override(self):
        # Letter dated Monday 1st, but franked/posted Wednesday 3rd
        letter_d = D(2026, 6, 1)
        posted_d = D(2026, 6, 3)
        res = deadline(letter_d, posted_on=posted_d)
        assert res["bekanntgabe"] == D(2026, 6, 7)  # 3 + 4 days

    def test_deadline_actual_receipt_scenarios(self):
        letter_d = D(2026, 7, 1)
        bekanntgabe_fictional = D(2026, 7, 5)

        # Arrived earlier than fiction: fiction protects citizen (stays at 5th)
        res_early = deadline(letter_d, received_on=D(2026, 7, 3))
        assert res_early["bekanntgabe"] == bekanntgabe_fictional

        # Arrived exact day of fiction: stays at 5th
        res_exact = deadline(letter_d, received_on=D(2026, 7, 5))
        assert res_exact["bekanntgabe"] == bekanntgabe_fictional

        # Arrived significantly late (post delay): moves to actual receipt date
        res_late = deadline(letter_d, received_on=D(2026, 7, 12))
        assert res_late["bekanntgabe"] == D(2026, 7, 12)
        assert res_late["deadline"] == next_working_day(D(2026, 8, 12))

    def test_deadline_multi_month_periods(self):
        letter_d = D(2026, 1, 10)
        # 3-month legal period (e.g. Klagefrist in special administrative proceedings)
        res_3m = deadline(letter_d, months=3)
        assert res_3m["bekanntgabe"] == D(2026, 1, 14)
        assert res_3m["deadline"] == next_working_day(D(2026, 4, 14))

        # 12-month period (e.g. lack of proper legal remedies instruction - § 58 Abs. 2 VwGO)
        res_12m = deadline(letter_d, months=12)
        assert res_12m["bekanntgabe"] == D(2026, 1, 14)
        assert res_12m["deadline"] == next_working_day(D(2027, 1, 14))

    def test_target_safety_margin_invariance(self):
        # Target must ALWAYS be exactly 7 calendar days before deadline
        for month in range(1, 13):
            res = deadline(D(2026, month, 15))
            assert res["target"] == res["deadline"] - dt.timedelta(days=7)
            assert res["target"] < res["deadline"]
