"""The demo clock.

The weekly loop takes weeks to play out, and a grader has minutes. So "today"
is a value the app stores, not what the wall clock says, and the UI can move it
forward a week at a time to walk through a block of the curriculum.

Everything that writes a date goes through `today()`. Nothing calls
`date.today()` directly, or the seeded history and new entries end up on
different calendars.
"""

from __future__ import annotations

from datetime import date, timedelta

from core import db

SETTING_KEY = "simulated_today"
# Week 1 of the seeded block. Twelve weeks of drive/boast/drop/lob puts the
# three Drop Weeks eight weeks apart and lands the final day on DEFAULT_TODAY,
# so the record covers August to mid-October and nothing sits in the future.
BLOCK_START = date(2026, 7, 27)   # a Monday
DEFAULT_TODAY = date(2026, 10, 18)


def today() -> date:
    raw = db.get_setting(SETTING_KEY)
    if not raw:
        return DEFAULT_TODAY
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return DEFAULT_TODAY


def today_iso() -> str:
    return today().isoformat()


def set_today(value: date | str) -> date:
    new = date.fromisoformat(value) if isinstance(value, str) else value
    db.set_setting(SETTING_KEY, new.isoformat())
    return new


def shift(days: int) -> date:
    return set_today(today() + timedelta(days=days))


def monday_of(value: date | None = None) -> date:
    """Start of the curriculum week containing `value`."""
    day = value or today()
    return day - timedelta(days=day.weekday())


def reset() -> date:
    return set_today(DEFAULT_TODAY)
