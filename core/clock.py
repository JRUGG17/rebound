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
BLOCK_START = date(2026, 9, 7)  # a Monday; week 1 of the seeded twelve-week block
# The demo opens in week 11 — the third Drop Week of the block — so there are ten
# weeks of history behind it and the chronic-cue detection has something to find.
DEFAULT_TODAY = date(2026, 11, 16)


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
