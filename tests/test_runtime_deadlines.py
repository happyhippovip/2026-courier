import datetime as dt

from courier_runtime.deadlines import add_months, deadline, easter, holidays_niedersachsen

D = dt.date


def test_easter_and_lower_saxony_holidays():
    assert easter(2026) == D(2026, 4, 5) and easter(2027) == D(2027, 3, 28)
    h = holidays_niedersachsen(2026)
    assert D(2026, 10, 31) in h and D(2026, 4, 3) in h and D(2026, 5, 14) in h     # Reformationstag, Karfreitag, Himmelfahrt


def test_month_end_rule():
    assert add_months(D(2026, 1, 31), 1) == D(2026, 2, 28)
    assert add_months(D(2026, 12, 15), 1) == D(2027, 1, 15)


def test_bescheid_20_07_2026():
    r = deadline(D(2026, 7, 20))
    assert r["bekanntgabe"] == D(2026, 7, 24) and r["deadline"] == D(2026, 8, 24) and r["target"] == D(2026, 8, 17)


def test_end_on_weekend_or_holiday_moves_to_next_working_day():
    assert deadline(D(2026, 9, 27))["deadline"] == D(2026, 11, 2)    # 01.10 -> 01.11 is Sunday -> Monday 02.11
    assert deadline(D(2026, 9, 26))["deadline"] == D(2026, 10, 30)   # 30.09 -> 30.10 (Friday, normal day)
    assert deadline(D(2026, 11, 21))["deadline"] == D(2026, 12, 28)  # 25.11 -> 25.12 + 26.12 holidays, Sunday -> 28.12


def test_late_receipt_extends_early_receipt_does_not_shorten():
    assert deadline(D(2026, 7, 20), received_on=D(2026, 7, 21))["bekanntgabe"] == D(2026, 7, 24)
    assert deadline(D(2026, 7, 20), received_on=D(2026, 7, 30))["bekanntgabe"] == D(2026, 7, 30)
