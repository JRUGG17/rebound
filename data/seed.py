"""Seed data: one twelve-week block at the Plainsboro club.

Invented people, written to behave like real ones. Every player in the roster
exists to make one thing findable:

  Maya    chronic cue — "racket before feet" recurs across all three Drop Weeks
  Dev     coach contradiction — two coaches give opposite advice in one week
  Ellie   timing rule — a grip rebuild flagged during a competitive block
  Tomas   youngest, shortest entries, tests age-appropriate language
  Priya   private entries that must never reach a coach-facing agent
  Jonah   the control: nothing wrong, so false positives show up

Weeks run drive / boast / drop / lob, three times. Drop Weeks land on weeks
3, 7 and 11, so "three Drop Weeks running" is a true twelve-week span.

Idempotent: running it twice rebuilds from scratch rather than duplicating.
"""

from __future__ import annotations

from datetime import timedelta

from core import db
from core.clock import BLOCK_START

# ---------------------------------------------------------------- people

COACHES = [
    ("coach_stuart", "Stuart Baines", "Head coach. Technical, blunt, writes short notes."),
    ("coach_nia", "Nia Fletcher", "Movement and conditioning. Works the younger squad."),
    ("coach_rob", "Rob Castellano", "Tournament coach. Travels to events."),
]

PLAYERS = [
    ("maya", "Maya Okonkwo", 14),
    ("dev", "Dev Raghunathan", 11),
    ("ellie", "Ellie Brennan", 16),
    ("tomas", "Tomas Lindqvist", 9),
    ("priya", "Priya Shah", 17),
    ("jonah", "Jonah Weiss", 12),
]

PARENTS = [
    ("parent_okonkwo", "Adaeze Okonkwo", "maya"),
    ("parent_shah", "Hiren Shah", "priya"),
]

ROTATION = ["drive", "boast", "drop", "lob"]
THEME_NAMES = {
    "drive": "Drive Week",
    "boast": "Boast Week",
    "drop": "Drop Week",
    "lob": "Lob Week",
}

# ---------------------------------------------------------------- cue library
# Mirrors section 9 of the playbook. The Organizer tags entries against these.

CUES = [
    ("racket_before_feet", "Racket before feet", "technical"),
    ("step_then_swing", "Step then swing", "technical"),
    ("space_beside_ball", "Space next to the ball", "technical"),
    ("left_arm", "Left arm engaged", "technical"),
    ("squeeze_grip", "Squeeze the grip", "technical"),
    ("follow_through", "Follow through to a target", "technical"),
    ("effect_on_ball", "Put effect on the ball", "technical"),
    ("hunt_volley", "Hunt the volley", "tactical"),
    ("aim_the_drive", "Aim the drive", "tactical"),
    ("get_lower", "Get lower", "physical"),
    ("watch_them_hit", "Watch them hit", "tactical"),
    ("responsible_pressure", "Responsible under pressure", "psychological"),
]


def week_start(week_no: int) -> str:
    """ISO date for the Monday of week `week_no` (1-based)."""
    return (BLOCK_START + timedelta(weeks=week_no - 1)).isoformat()


def day_in_week(week_no: int, weekday: int) -> str:
    """ISO date for a given weekday (0=Mon) inside week `week_no`."""
    return (BLOCK_START + timedelta(weeks=week_no - 1, days=weekday)).isoformat()


# ---------------------------------------------------------------- entries
#
# (week, weekday, player, author, setting, rung, shot, category, cue, visibility, text)
# Author "self" means the player wrote it. An optional twelfth element is the
# kid-facing rewrite of a coach note — same entry, two renderings.
ENTRIES: list[tuple] = [

    # ---------------- Maya: the chronic cue, and a lob that will not transfer
    (3, 1, "maya", "coach_stuart", "lesson", None, "drop", "technical",
     "racket_before_feet", "shared",
     "Focus for the next few weeks: racket before feet. She is moving first and "
     "preparing late, so everything in the front is rushed. Showed her the early twitch.",
     "This month we're working on getting your racket up BEFORE you move. Right now "
     "your feet go first and your racket catches up late, which is why the front of "
     "the court feels rushed. Racket first, then run."),
    (3, 2, "maya", "coach_stuart", "squad", "block", "drop", "technical",
     "racket_before_feet", "shared",
     "Blocked drop work — prep was early and clean all session. Looked solved."),
    (3, 3, "maya", "coach_stuart", "squad", "conditioned_game", "drop", "technical",
     "racket_before_feet", "shared",
     "Long/long/short with dead quarters. Prep gone completely, feet first every rally. "
     "She cannot hold it once she has decisions to make."),
    (3, 3, "maya", "self", "reflection", "conditioned_game", "drop", "psychological",
     None, "shared",
     "the blocked stuff felt good today but in the game i just forgot about it, "
     "was thinking about where to hit it"),

    (7, 1, "maya", "coach_stuart", "lesson", None, "drop", "technical",
     "racket_before_feet", "shared",
     "Back to racket before feet. Same as four weeks ago. Fine when she is thinking "
     "about it, gone when she is not."),
    (7, 3, "maya", "coach_nia", "squad", "pattern", "drop", "technical",
     "racket_before_feet", "shared",
     "Drive/drop strict pattern. Prep held for the first few then drifted late."),
    (7, 4, "maya", "self", "reflection", None, "drop", "technical", None, "shared",
     "coach said racket before feet again. i thought i fixed this"),

    (11, 1, "maya", "coach_stuart", "lesson", None, "drop", "technical",
     "racket_before_feet", "shared",
     "Third Drop Week running on the same cue. Not a reminder any more. Something "
     "else is going on — possibly she cannot see the ball early enough to start."),

    # Maya's lob: clean low on the ladder, gone high
    (4, 2, "maya", "coach_nia", "squad", "block", "lob", "tactical",
     None, "shared",
     "Cross lob blocks — height was good, nothing touching the side wall. Textbook."),
    (4, 3, "maya", "coach_nia", "squad", "routine", "lob", "tactical", None, "shared",
     "Drive/boast/cross-lob routine, diagonals. Still holding up well."),
    (8, 4, "maya", "coach_nia", "squad", "conditioned_game", "lob", "tactical",
     None, "shared",
     "Went for the side wall under pressure three times, two went out. Under pressure "
     "she reverts to the thing we tell them not to do."),
    (8, 5, "maya", "coach_rob", "tournament", "match", "lob", "tactical", None, "shared",
     "Lost 3-1 at the Mid-Atlantic qualifier. Same lob problem — every reset went for "
     "the nick and she could not get out of the back."),

    # ---------------- Dev: two coaches, opposite advice, same week
    (6, 1, "dev", "coach_stuart", "lesson", None, "boast", "technical",
     "follow_through", "shared",
     "Swing is far too big for an eleven-year-old boast. Shortened him right down — "
     "compact, controlled, let the rotation do it."),
    (6, 3, "dev", "coach_nia", "squad", "routine", "boast", "technical",
     "follow_through", "shared",
     "Told him to let the follow through go — he is cutting the swing off early and "
     "the ball dies before the side wall. Needs more through the shot."),
    (6, 4, "dev", "self", "reflection", None, "boast", "psychological", None, "shared",
     "stuart said smaller swing and nia said bigger follow through. i dont know "
     "which one to do so i just did what i normally do"),
    (10, 2, "dev", "coach_nia", "squad", "block", "boast", "technical", None, "shared",
     "Still inconsistent on the boast. Hard to tell what he is trying to do."),

    # ---------------- Ellie: grip rebuild flagged mid competitive season
    (2, 1, "ellie", "coach_stuart", "lesson", None, "drive", "technical",
     "squeeze_grip", "shared",
     "Her grip is too far into the palm. It is costing her racket face control on "
     "everything. Proper fix is a rebuild, but she has states in six weeks — "
     "not touching it now. Logging it for the off-season."),
    (2, 1, "ellie", "coach_stuart", "lesson", None, "drive", "technical",
     None, "private",
     "Long term the grip has to change or she will plateau at this level. Needs a "
     "conversation with her and her parents about when, probably April."),
    (5, 3, "ellie", "coach_stuart", "squad", "pattern", "drive", "technical",
     "squeeze_grip", "shared",
     "Racket face opening up on the backhand again under pace. Same root cause. "
     "Working around it for now — aiming higher and tighter instead."),
    (9, 2, "ellie", "coach_rob", "tournament", "match", "drive", "tactical",
     "aim_the_drive", "shared",
     "Won her group at the Philadelphia Open. Drives were a foot off the wall all "
     "day but she played the percentages and it held up."),
    (8, 3, "ellie", "coach_nia", "squad", "block", "drive", "technical",
     "squeeze_grip", "shared",
     "Blocked drives — the face is still opening up as soon as there is any pace on "
     "the ball. It is the grip, same as always. Nothing to do about it this term."),
    (11, 2, "ellie", "self", "reflection", None, "drive", "technical", None, "shared",
     "backhand still feels loose when they hit it hard at me. been like this all season"),
    (11, 3, "ellie", "coach_stuart", "squad", "pattern", "drive", "technical",
     "squeeze_grip", "shared",
     "Fourth time this block I have written the same thing about her grip. She is "
     "managing around it well and winning matches, but it is a ceiling."),

    # ---------------- Tomas: nine, short entries, age-appropriate
    (1, 2, "tomas", "coach_nia", "squad", "block", "drive", "technical",
     "step_then_swing", "shared",
     "Nine years old, first full block. Working on step then swing — he swings "
     "standing still. Keep it to one thing at a time.",
     "Step, THEN hit. One big step before you swing. That's the only thing to "
     "remember today!"),
    (1, 2, "tomas", "self", "reflection", None, "drive", "technical", None, "shared",
     "i did the stepping thing. it was fun"),
    (5, 2, "tomas", "coach_nia", "squad", "block", "drive", "technical",
     "step_then_swing", "shared",
     "Stepping in now without being told. Big improvement for four weeks."),
    (5, 2, "tomas", "self", "reflection", None, "drive", "psychological", None, "shared",
     "i won a point against a big kid"),
    (9, 2, "tomas", "coach_nia", "squad", "routine", "drive", "physical",
     "get_lower", "shared",
     "Ready for routines now. Next thing is getting lower — he is very upright."),

    # ---------------- Priya: private entries. These must never reach a coach agent.
    (4, 1, "priya", "coach_stuart", "lesson", None, "lob", "technical",
     "effect_on_ball", "shared",
     "Lob is flat and quick — needs more height and more under the ball. "
     "Recruiting year, so keeping the changes small.",
     "Your lob is coming out flat and fast, so it isn't buying you the time you "
     "need. More height, and get under the ball more. Small change, nothing drastic "
     "— this is your season."),
    (4, 2, "priya", "self", "reflection", None, "lob", "psychological", None, "private",
     "honestly i have been dreading squad all week. every session feels like a "
     "trial for college coaches and i cannot enjoy playing any more. i do not want "
     "stuart to know i feel like this"),
    (6, 3, "priya", "self", "reflection", None, "boast", "technical", None, "shared",
     "boast felt much better today, the rotation thing clicked"),
    (8, 2, "priya", "self", "reflection", None, None, "psychological", None, "private",
     "did not sleep before the qualifier. kept thinking about messing up in front "
     "of the coach from Trinity"),
    (8, 4, "priya", "coach_rob", "tournament", "match", "lob", "tactical",
     None, "shared",
     "Semi-final at the qualifier. Very tight, lost 3-2. Tactically excellent, "
     "seemed tense between games but would not say much."),
    (10, 1, "priya", "coach_stuart", "lesson", None, "lob", "technical",
     "effect_on_ball", "shared",
     "Height is better. Still quite flat when she is rushed."),

    # ---------------- Jonah: the control. Nothing is wrong here.
    (2, 2, "jonah", "coach_nia", "squad", "routine", "drive", "technical",
     "left_arm", "shared",
     "Left arm doing nothing on the backhand. Showed him the counterbalance."),
    (6, 2, "jonah", "coach_nia", "squad", "pattern", "boast", "technical",
     "left_arm", "shared",
     "Left arm is in now, and it has stuck in patterns too. Good four weeks."),
    (10, 3, "jonah", "coach_nia", "squad", "conditioned_game", "boast", "technical",
     None, "shared",
     "Holding up in conditioned games. Nothing to fix — give him harder drills."),
    (10, 4, "jonah", "self", "reflection", None, "boast", "psychological", None, "shared",
     "feeling good about my boast, want to try it more in matches"),
]

FOCUSES = [
    ("maya", "coach_stuart", "Racket before feet — early twitch on the backhand",
     "technical", "racket_before_feet", 3),
    ("dev", "coach_stuart", "Compact swing on the boast", "technical", "follow_through", 6),
    ("ellie", "coach_stuart", "Hold the racket face under pace — grip rebuild deferred",
     "technical", "squeeze_grip", 2),
    ("tomas", "coach_nia", "Step then swing", "technical", "step_then_swing", 1),
    ("priya", "coach_stuart", "More height and more under the ball on the lob",
     "technical", "effect_on_ball", 4),
    ("jonah", "coach_nia", "Left arm as a counterbalance on the backhand",
     "technical", "left_arm", 2),
]


def build(*, reset: bool = True) -> dict:
    """Create the database and fill it. Returns a count of what was written."""
    db.init_db()

    if reset:
        with db.connect() as conn:
            for table in ("entries", "focuses", "cues", "people", "weeks", "settings"):
                conn.execute(f"DELETE FROM {table}")

    with db.connect() as conn:
        for pid, name, _bio in COACHES:
            conn.execute(
                "INSERT INTO people (id, name, role, joined_on) VALUES (?,?,'coach',?)",
                (pid, name, BLOCK_START.isoformat()),
            )
        for pid, name, age in PLAYERS:
            conn.execute(
                "INSERT INTO people (id, name, role, age, joined_on) VALUES (?,?,'player',?,?)",
                (pid, name, age, BLOCK_START.isoformat()),
            )
        for pid, name, child in PARENTS:
            conn.execute(
                "INSERT INTO people (id, name, role, child_id, joined_on) "
                "VALUES (?,?,'parent',?,?)",
                (pid, name, child, BLOCK_START.isoformat()),
            )
        for cue_id, canonical, category in CUES:
            conn.execute("INSERT INTO cues (id, canonical, category) VALUES (?,?,?)",
                         (cue_id, canonical, category))

        for week_no in range(1, 13):
            shot = ROTATION[(week_no - 1) % 4]
            conn.execute(
                """INSERT INTO weeks (id, starts_on, theme_shot, theme_name, block_no, cycle_no)
                   VALUES (?,?,?,?,1,?)""",
                (week_no, week_start(week_no), shot, THEME_NAMES[shot],
                 (week_no - 1) // 4 + 1),
            )

    for row in ENTRIES:
        week_no, weekday, player, author, setting, rung, shot, category, cue, vis, text = row[:11]
        author_id = player if author == "self" else author
        db.add_entry(
            player_id=player,
            author_id=author_id,
            author_role="player" if author == "self" else "coach",
            setting=setting,
            rung=rung,
            shot=shot,
            category=category,
            cue_id=cue,
            raw_text=text,
            player_text=row[11] if len(row) > 11 else None,
            # Seeded rewrites are pre-approved by their author — they stand for
            # notes the coach already read and released.
            approved_by=author_id if len(row) > 11 else None,
            visibility=vis,
            occurred_on=day_in_week(week_no, weekday),
        )

    with db.connect() as conn:
        for player, coach, text, category, cue, week_no in FOCUSES:
            conn.execute(
                """INSERT INTO focuses (player_id, coach_id, text, category, cue_id, set_on)
                   VALUES (?,?,?,?,?,?)""",
                (player, coach, text, category, cue, day_in_week(week_no, 1)),
            )

    with db.connect() as conn:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            for table in ("people", "weeks", "entries", "focuses", "cues")
        }
    return counts


if __name__ == "__main__":
    for table, count in build().items():
        print(f"  {count:>4}  {table}")
    print(f"\n  database: {db.DB_PATH}")
