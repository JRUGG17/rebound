"""Phase 2 check: schema, seed data, the demo clock, and the visibility boundary.

No model calls, so this is free and deterministic. The visibility section is the
one that matters — it is the evidence for the report's safety row.

Run:  ./venv/bin/python scripts/check_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import clock, db  # noqa: E402
from data import seed  # noqa: E402


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{f'  — {detail}' if detail else ''}")
    if not ok:
        check.failed += 1
    return ok


check.failed = 0

# Lines only Priya can see. If one of these ever shows up coach-side, the app
# has broken its central promise, so they are checked by content, not by flag.
SECRETS = ["dreading squad", "cannot enjoy playing", "did not sleep", "Trinity"]


def seed_report() -> dict:
    print("\n[1] Schema and seed")
    counts = seed.build()
    for table, n in counts.items():
        print(f"        {n:>4}  {table}")
    check("players seeded", counts["people"] >= 9)
    check("twelve weeks of curriculum", counts["weeks"] == 12)
    check("entries seeded", counts["entries"] > 30)
    return counts


def rotation_report() -> None:
    print("\n[2] Curriculum rotation")
    with db.connect() as conn:
        weeks = conn.execute("SELECT * FROM weeks ORDER BY id").fetchall()
    shots = [w["theme_shot"] for w in weeks]
    print(f"        {' → '.join(s[:2] for s in shots)}")
    check("no shot runs two weeks running",
          all(a != b for a, b in zip(shots, shots[1:])))
    drop_weeks = [w["id"] for w in weeks if w["theme_shot"] == "drop"]
    check("three Drop Weeks in the block", len(drop_weeks) == 3, f"weeks {drop_weeks}")
    check("they span eight weeks", drop_weeks[-1] - drop_weeks[0] == 8)

    with db.connect() as conn:
        latest = conn.execute("SELECT MAX(occurred_on) AS d FROM entries").fetchone()["d"]
    check("nothing is dated in the future", latest <= clock.today_iso(),
          f"latest entry {latest}, today {clock.today_iso()}")


def clock_report() -> None:
    print("\n[3] Demo clock")
    clock.reset()
    start = clock.today()
    week = db.week_of(clock.today_iso())
    check("today resolves to a curriculum week", week is not None,
          f"{start} → week {week['id']}, {week['theme_name']}" if week else "")
    check("it opens on the last day of the block", bool(week) and week["id"] == 12)
    # The chronic-cue demo needs the third Drop Week to be recent history, not
    # today — a coach looking back at it is the situation being shown.
    with db.connect() as conn:
        last_drop = conn.execute(
            "SELECT * FROM weeks WHERE theme_shot = 'drop' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    check("the last Drop Week is recent", last_drop["id"] == 11,
          f"week {last_drop['id']}, starting {last_drop['starts_on']}")
    clock.shift(7)
    check("clock moves forward a week", clock.today() > start, str(clock.today()))
    clock.reset()
    check("clock resets", clock.today() == start)


def visibility_report() -> None:
    print("\n[4] Visibility boundary")

    coach_side = db.entries_for_coach("priya")
    player_side = db.entries_for_player("priya")
    parent_side = db.entries_for_parent("priya")

    private = [e for e in player_side if e["visibility"] == "private"]
    check("Priya has private entries to protect", len(private) >= 2, f"{len(private)} found")

    coach_text = " ".join(e["raw_text"] for e in coach_side).lower()
    leaked = [s for s in SECRETS if s.lower() in coach_text]
    check("no private text reaches the coach view", not leaked, f"leaked: {leaked}")

    parent_text = " ".join(e["raw_text"] for e in parent_side).lower()
    check("no private text reaches the parent view",
          not any(s.lower() in parent_text for s in SECRETS))

    check("the player still sees their own private entries",
          any("dreading squad" in e["raw_text"] for e in player_side))

    # A coach's private note is for coaches, and not for the player or parent.
    ellie_coach = db.entries_for_coach("ellie")
    ellie_player = db.entries_for_player("ellie")
    ellie_parent = db.entries_for_parent("ellie")
    check("coaches see each other's private notes",
          any(e["visibility"] == "private" for e in ellie_coach))
    check("the player does not see a coach's private note",
          not any(e["visibility"] == "private" for e in ellie_player))
    check("the parent does not see a coach's private note",
          not any(e["visibility"] == "private" for e in ellie_parent))

    # Same entry, two renderings: the coach's own words, and the kid's version.
    # Most term notes are written to the player already, so coach text and
    # player text are the same string by design. The pair that matters is a
    # note written in coach voice with a separate version for the kid.
    note = next(e for e in db.entries_for_coach("maya")
                if e["author_role"] == "coach" and e["player_text"]
                and e["player_text_approved_at"]
                and e["player_text"] != e["raw_text"])
    coach_view = db.render_for(note, "coach")
    kid_view = db.render_for(note, "player")
    check("a coach note renders differently for the kid", coach_view != kid_view)
    check("the coach reads their own words",
          coach_view == note["raw_text"], coach_view[:48] + "…")
    check("the kid reads the rewrite",
          kid_view == note["player_text"], kid_view[:48] + "…")

    kid_own = next(e for e in db.entries_for_player("maya") if e["author_role"] == "player")
    check("a kid's own words are never rewritten at them",
          db.render_for(kid_own, "player") == kid_own["raw_text"])

    # --- the human in the loop -------------------------------------------
    # A model's paraphrase can drop a qualifier the coach meant to keep, and
    # the coach would never notice because they only ever see their own text.
    # So nothing reaches a child until that coach has read the rewrite.
    print()
    # Most seeded coach notes now ship with a released player version, so the
    # unreleased ones live on whichever player the seed left pending.
    unreleased = next(
        (e for p in db.people("player") for e in db.entries_for_coach(p["id"])
         if e["author_role"] == "coach" and not e["player_text_approved_at"]), None)
    if not check("the seed leaves something unreleased", unreleased is not None):
        return
    subject = unreleased["player_id"]
    check("an unapproved rewrite is withheld from the kid",
          db.render_for(unreleased, "player") is None)
    check("...and the coach still has their own note",
          db.render_for(unreleased, "coach") == unreleased["raw_text"])
    check("...and it does not appear in the kid's feed at all",
          unreleased["id"] not in {e["id"] for e in db.entries_for_player(subject)})
    check("...nor in the parent's",
          unreleased["id"] not in {e["id"] for e in db.entries_for_parent(subject)})

    author = unreleased["author_id"]
    queue = db.pending_approval(author)
    check("the coach has an approval queue", len(queue) > 0, f"{len(queue)} waiting")

    db.approve_player_text(unreleased["id"], author,
                           edited="Rewritten by the coach, not the model.")
    released = next(e for e in db.entries_for_player(subject) if e["id"] == unreleased["id"])
    check("approving releases it to the kid",
          db.render_for(released, "player") == "Rewritten by the coach, not the model.")
    check("the coach's edit is what shipped, not the model's",
          released["player_text"] == "Rewritten by the coach, not the model.")
    check("the approval is attributed",
          released["player_text_approved_by"] == author)
    check("the original note is untouched",
          released["raw_text"] == unreleased["raw_text"])
    check("the queue shrinks",
          len(db.pending_approval(author)) == len(queue) - 1)
    print()

    # The role dispatcher must not let one player read another.
    check("a player cannot read another player",
          db.visible_to("maya", "priya") == [])
    check("a parent cannot read someone else's child",
          db.visible_to("parent_okonkwo", "priya") == [])
    check("a parent can read their own child",
          len(db.visible_to("parent_okonkwo", "maya")) > 0)


def findings_report() -> None:
    print("\n[5] The things the Comparison agent has to find")

    maya = db.entries_for_coach("maya")
    chronic = [e for e in maya if e["cue_id"] == "racket_before_feet"]
    weeks_hit = sorted({db.week_of(e["occurred_on"])["id"] for e in chronic})
    check("Maya's cue recurs across three Drop Weeks", len(weeks_hit) >= 3,
          f"weeks {weeks_hit}")

    lob = [e for e in maya if e["shot"] == "lob" and e["rung"]]
    low = [e for e in lob if e["rung"] in ("block", "routine")]
    high = [e for e in lob if e["rung"] in ("conditioned_game", "match")]
    check("Maya's lob has entries low and high on the ladder",
          bool(low) and bool(high), f"{len(low)} low, {len(high)} high")

    dev = db.entries_for_coach("dev")
    week6 = [e for e in dev if db.week_of(e["occurred_on"])["id"] == 6
             and e["author_role"] == "coach"]
    authors = {e["author_id"] for e in week6}
    check("two coaches advised Dev in the same week", len(authors) >= 2,
          ", ".join(sorted(authors)))

    ellie = db.entries_for_coach("ellie")
    check("Ellie's deferred grip rebuild is on file",
          any("off-season" in e["raw_text"] or "April" in e["raw_text"] for e in ellie))

    jonah = db.entries_for_coach("jonah")
    check("Jonah is clean, as a false-positive control",
          not any("still" in e["raw_text"].lower() for e in jonah))


def main() -> int:
    print("=" * 64)
    print("Rebound — Phase 2 check")
    print("=" * 64)
    seed_report()
    rotation_report()
    clock_report()
    visibility_report()
    findings_report()
    print("\n" + "=" * 64)
    print("ALL PASS" if not check.failed else f"{check.failed} FAILED")
    return 1 if check.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
