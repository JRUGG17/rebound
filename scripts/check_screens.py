"""Render every screen for every role, and fail if any of them raises.

This exists because a NameError in a view function sat in the app for
several commits without being noticed. Importing the module succeeded, the
callbacks registered, the test suite passed — and the page 500'd the moment
anyone clicked it, because nothing had ever called the function.

No model calls, no server. It calls the view functions the way the router
does and checks they return a tree.

Run:  ./venv/bin/python scripts/check_screens.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import coach_views as cv  # noqa: E402
from core import clock, db  # noqa: E402
from data import seed  # noqa: E402

import app as application  # noqa: E402


def check(label: str, fn) -> None:
    try:
        tree = fn()
    except Exception as exc:  # noqa: BLE001 — the whole point is catching these
        print(f"  FAIL  {label}  — {type(exc).__name__}: {exc}")
        check.failed += 1
        return
    if tree is None:
        print(f"  FAIL  {label}  — returned None")
        check.failed += 1
        return
    print(f"  PASS  {label}")


check.failed = 0


ARC = {
    "overview": "Three terms on the backhand drive.",
    "phases": [{"span": "Aug 3 – Sep 1", "focus": "length off the back wall",
                "what_happened": "Your coaches wrote that it shortened."}],
    "carried_over": ["racket before feet, nine lessons apart"],
    "never_answered": ["whether to change grip on the volley"],
}


def main() -> int:
    print("=" * 64)
    print("Rebound — every screen renders")
    print("=" * 64)
    seed.build()
    clock.reset()
    today = clock.today_iso()
    player, coach, parent = "maya", "coach_stuart", "parent_okonkwo"

    print("\n[player]")
    check("today", lambda: application.player_today(player))
    check("reflections", lambda: application.player_reflections(player, "shared", None))
    check("lessons by month",
          lambda: cv.lesson_months(player, None, "player", None, None, None, False))
    for key, _label in cv.RANGES:
        check(f"recap, {key}", lambda k=key: cv.recap_panel(player, "player", k, None, False))
    check("recap with a result", lambda: cv.recap_panel(
        player, "player", "30",
        {"headline": "h", "overview": "o", "emphasis": "technical",
         "themes": [{"title": "t", "category": "technical", "cue_id": None,
                     "direction": "flat", "what_it_is": "w", "evidence": "e"}],
         "gap": "g"}, False))
    check("lesson picker, searching the roster",
          lambda: cv.coach_lesson_picker(coach, "ma"))
    check("lesson picker, search matches nobody",
          lambda: cv.coach_lesson_picker(coach, "zzzz"))
    check("recap, everything on file",
          lambda: cv.recap_panel(player, "player", "all", None, False, True))
    check("recap, a year picked",
          lambda: cv.recap_panel(player, "player", "all", None, False, True,
                                 year=2026))
    check("recap, a year with nothing in it",
          lambda: cv.recap_panel(player, "player", "all", None, False, True,
                                 year=1999))
    check("lesson thread, running",
          lambda: cv.lesson_months(player, None, "player", None, None, None,
                                   False, None, None, True))
    check("lesson thread, read back",
          lambda: cv.lesson_months(player, None, "player", None, None, None,
                                   False, None, ARC, False))
    check("lesson thread with nothing carried over",
          lambda: cv.lesson_arc_card({**ARC, "carried_over": [],
                                      "never_answered": []}, False, "coach"))
    check("recap summary", lambda: cv.recap_summary(player, "player", "30", None, False))
    check("recap summary with a result",
          lambda: cv.recap_summary(player, "player", "30",
                                   {"headline": "h", "overview": "o"}, False))
    check("usage", application.usage_page)

    print("\n[coach]")
    check("today", lambda: cv.coach_today(coach))
    check("today with a saved theme", lambda: cv.coach_today(coach, "Set to Drop Week."))
    check("roster", cv.roster)
    check("roster with the add form open", lambda: cv.roster(None, True))
    check("player detail", lambda: cv.player_detail(player, None, False))
    check("player detail with findings", lambda: cv.player_detail(
        player, {"summary": "s", "findings": [
            {"kind": "chronic_cue", "headline": "h", "evidence": "e",
             "confidence": "high", "timing_caution": "t", "for_the_coach": "f"}]},
        False))
    check("player detail with a focus message",
          lambda: cv.player_detail(player, None, False, "Set."))
    check("add note, empty", lambda: cv.note_composer(None, False))
    check("add note, prefilled for a lesson", lambda: cv.note_composer(
        {"player_id": player, "setting": "lesson", "on": "2026-10-13",
         "text": "", "organized": None}, False))
    check("add note, filed", lambda: cv.note_composer(
        {"player_id": player, "setting": "lesson", "text": "note",
         "organized": {"category": "technical", "summary": "s", "rung": "block",
                       "shot": "drop", "cue_id": None, "proposed_cue": None,
                       "send_warning": "careful", "mentions_injury": True}}, False))
    check("coach resources", lambda: cv.resources(None, False, 1))
    check("coach resources with an answer", lambda: cv.resources(
        {"answer": "a", "citations": ["§3"], "in_playbook": True,
         "note_for_admin": "n"}, False, 3))
    check("my lessons picker", lambda: cv.coach_lesson_picker(coach))
    check("picker for a coach who teaches nobody",
          lambda: cv.coach_lesson_picker("coach_rob"))
    check("a player's lessons by month",
          lambda: cv.lesson_months(player, coach, "coach", None, None, None, False))
    check("...with a lesson open",
          lambda: cv.lesson_months(player, coach, "coach", None, None,
                                   "2026-10-19", False))
    check("...for a year with nothing in it",
          lambda: cv.lesson_months(player, coach, "coach", None, 2019, None, False))
    check("a player's recap", lambda: cv.recap_panel(player, "coach", "30", None, False))
    check("the courtside glance", lambda: cv.player_detail(player, None, False))
    check("focus pair, coach side", lambda: cv.focus_pair(player, "coach"))
    check("focus pair, editing", lambda: cv.focus_pair(player, "coach", None, "coach"))
    check("focus pair, history open",
          lambda: cv.focus_pair(player, "coach", None, None, "coach"))
    check("focus pair, player side", lambda: cv.focus_pair(player, "player"))
    check("recap with entries shown",
          lambda: cv.recap_panel(player, "player", "30", None, False, True))
    check("recap filtered to lessons",
          lambda: cv.recap_panel(player, "player", "30", None, False, True, "lesson"))
    check("recap filtered to one coach",
          lambda: cv.recap_panel(player, "coach", "30", None, False, True,
                                 None, "coach_stuart"))
    check("recap filtered to nothing at all",
          lambda: cv.recap_panel(player, "player", "7", None, False, True, "solo"))
    check("week card", lambda: cv.week_card(coach))
    check("week card, editing", lambda: cv.week_card(coach, None, True))
    check("player detail, admin can remove",
          lambda: cv.player_detail(player, None, False, None, None, None, True))
    check("needs-you card", lambda: cv.attention_card(coach))
    check("roster search finds nothing",
          lambda: cv.roster("zzzznothing"))

    print("\n[parent]")
    check("parent page", lambda: cv.parent_page(parent))

    print("\n[edge cases]")
    empty = "coach_rob"
    check("a player with no entries in the window",
          lambda: cv.recap_panel(player, "player", "7", None, False))


    print("\n" + "=" * 64)
    print("ALL PASS" if not check.failed else f"{check.failed} FAILED")
    return 1 if check.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
