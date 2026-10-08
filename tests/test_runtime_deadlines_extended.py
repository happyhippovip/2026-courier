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


def test_next_working_day_consecutive_holidays():
    # Easter 2026 is April 5 (Sunday). Karfreitag is April 3 (Friday).
    # Ostermontag is April 6 (Monday).
    # Starting on Karfreitag (April 3): next working day must be Dienstag (April 7).
    karfreitag = D(2026, 4, 3)
    tuesday = next_working_day(karfreitag)
    assert tuesday == D(2026, 4, 7)
    assert tuesday.weekday() == 1  # Tuesday


def test_multi_month_and_year_transition():
    # 3-month deadline
    start = D(2026, 10, 15)
    r = deadline(start, months=3, fiction_days=0)
    # 2026-10-15 + 3 months -> 2027-01-15 (Friday, work day)
    assert r["bekanntgabe"] == start
    assert r["deadline"] == D(2027, 1, 15)
    assert r["target"] == D(2027, 1, 8)


def test_leap_year_handling():
    # 2028 is a leap year. Feb 29 exists.
    assert add_months(D(2028, 1, 31), 1) == D(2028, 2, 29)
    # Non-leap year 2027
    assert add_months(D(2027, 1, 31), 1) == D(2027, 2, 28)


def test_custom_posted_on_and_fiction_days():
    letter_date = D(2026, 6, 1)
    posted_on = D(2026, 6, 5)
    # 3 days fiction
    r = deadline(letter_date, posted_on=posted_on, fiction_days=3)
    assert r["bekanntgabe"] == D(2026, 6, 8)  # June 5 + 3 days
    # June 8 + 1 month -> July 8
    assert r["deadline"] == D(2026, 7, 8)
    assert r["target"] == D(2026, 7, 1)


def test_target_is_always_seven_days_before_deadline():
    dates_to_test = [
        D(2026, 1, 1),
        D(2026, 5, 20),
        D(2026, 12, 20),
        D(2027, 3, 10),
    ]
    for d in dates_to_test:
        res = deadline(d)
        assert res["target"] == res["deadline"] - dt.timedelta(days=7)
