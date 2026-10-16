"""Deadline calculator for official German letters (Bescheide).

Rules used (general information, not legal advice; the letter's own
Rechtsbehelfsbelehrung always wins):
- Bekanntgabe-Fiktion: a letter sent by post counts as received on the
  4th day after it was posted (since 2025; before: 3rd day). The letter date
  is used as the posting date unless a later posting date is known.
- A one-month deadline ends on the day of the following month with the same
  number; if that day does not exist, on the month's last day.
- If the end falls on a Saturday, Sunday or public holiday, it moves to the
  next working day. Holidays: nationwide + Lower Saxony (Reformationstag).
- `target` is a safety date one week earlier: act by then, never at the edge.
"""
import calendar
import datetime as dt


def easter(year):
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    return dt.date(year, month, day)


def holidays_niedersachsen(year):
    e = easter(year)
    return {dt.date(year, 1, 1), e - dt.timedelta(days=2), e + dt.timedelta(days=1), dt.date(year, 5, 1),
            e + dt.timedelta(days=39), e + dt.timedelta(days=50), dt.date(year, 10, 3), dt.date(year, 10, 31),
            dt.date(year, 12, 25), dt.date(year, 12, 26)}


def next_working_day(day):
    while day.weekday() >= 5 or day in holidays_niedersachsen(day.year):
        day += dt.timedelta(days=1)
    return day


def add_months(day, months):
    month0 = day.month - 1 + months
    year, month = day.year + month0 // 12, month0 % 12 + 1
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def deadline(letter_date, months=1, posted_on=None, fiction_days=4, received_on=None):
    """Return dict with bekanntgabe, deadline (legal end) and target (one week earlier).
    A later actual receipt moves Bekanntgabe later; an earlier one never shortens it."""
    posted = posted_on or letter_date
    bekanntgabe = posted + dt.timedelta(days=fiction_days)
    if received_on and received_on > bekanntgabe:
        bekanntgabe = received_on
    end = next_working_day(add_months(bekanntgabe, months))
    return {"bekanntgabe": bekanntgabe, "deadline": end, "target": end - dt.timedelta(days=7)}
