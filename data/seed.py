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

# Head of program development. The only role that can edit the playbook, which
# is the only way the agents' knowledge ever changes.
ADMINS = [
    ("admin_jamie", "Jamie Ruggiero"),
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
     "Focus for the next few weeks: racket before feet. Right now your feet go first "
     "and the racket catches up late, which is why the front of the court feels "
     "rushed. Racket first, then run.", "release"),
    (3, 2, "maya", "coach_stuart", "squad", "block", "drop", "technical",
     "racket_before_feet", "shared",
     "Blocked drop work — prep was early and clean all session. That is exactly it.", "release"),
    (3, 3, "maya", "coach_stuart", "squad", "conditioned_game", "drop", "technical",
     "racket_before_feet", "shared",
     "Long/long/short with dead quarters. Prep gone completely, feet first every "
     "rally. You cannot hold it yet once you have decisions to make.", "release"),
    (3, 3, "maya", "self", "reflection", "conditioned_game", "drop", "psychological",
     None, "shared",
     "the blocked stuff felt good today but in the game i just forgot about it, "
     "was thinking about where to hit it", "release"),

    (7, 1, "maya", "coach_stuart", "lesson", None, "drop", "technical",
     "racket_before_feet", "shared",
     "Back to racket before feet, same as four weeks ago. It is there when you are "
     "thinking about it and gone when you are not.", "release"),
    (7, 3, "maya", "coach_nia", "squad", "pattern", "drop", "technical",
     "racket_before_feet", "shared",
     "Drive/drop strict pattern. Prep held for the first few, then drifted late.", "release"),
    (7, 4, "maya", "self", "reflection", None, "drop", "technical", None, "shared",
     "coach said racket before feet again. i thought i fixed this", "release"),

    (11, 1, "maya", "coach_stuart", "lesson", None, "drop", "technical",
     "racket_before_feet", "shared",
     "Third Drop Week running on the same cue. This is not a reminder any more. "
     "Something else is going on — I think you may not be picking the ball up early "
     "enough to start the racket.", "release"),

    # Maya's lob: clean low on the ladder, gone high
    (4, 2, "maya", "coach_nia", "squad", "block", "lob", "tactical",
     None, "shared",
     "Cross lob blocks — height good, nothing touching the side wall. Textbook.", "release"),
    (4, 3, "maya", "coach_nia", "squad", "routine", "lob", "tactical", None, "shared",
     "Drive/boast/cross-lob routine on diagonals. Still holding up well.", "release"),
    (8, 4, "maya", "coach_nia", "squad", "conditioned_game", "lob", "tactical",
     None, "shared",
     "You went for the side wall under pressure three times and two went out. Under "
     "pressure you are going back to the thing we tell you not to do.", "release"),
    (8, 5, "maya", "coach_rob", "tournament", "match", "lob", "tactical", None, "shared",
     "Lost 3-1 at the Mid-Atlantic qualifier. Same lob problem — every reset went for "
     "the nick and you could not get out of the back.", "release"),

    # ---------------- Week 11, this week: what the squad is actually on.
    # Several players on the same cue is normal, and it is the whole point of
    # the squad card — the coach has two minutes on the bleachers and should
    # lead with whatever most of the group is working on.
    (11, 2, "priya", "coach_nia", "squad", "block", "drop", "technical",
     "racket_before_feet", "shared",
     "Prep is late on the drop when you are moving forward. Same note as half the group "
     "this week.", "release"),
    (11, 2, "jonah", "coach_nia", "squad", "block", "drop", "technical",
     "racket_before_feet", "shared",
     "Racket is coming up after the first step rather than before it.", "release"),
    (11, 3, "tomas", "coach_nia", "squad", "routine", "drop", "physical",
     "get_lower", "shared",
     "Very upright into the front corners. Soften the knees.", "release"),
    (11, 3, "dev", "coach_nia", "squad", "routine", "drop", "physical",
     "get_lower", "shared",
     "Standing tall on the drop, so you are reaching rather than stepping in.", "release"),

    # ---------------- Dev: two coaches, opposite advice, same week
    (6, 1, "dev", "coach_stuart", "lesson", None, "boast", "technical",
     "follow_through", "shared",
     "Boast swing is getting loose — too much arm and not much shape. Bring it back "
     "toward a drive swing, maybe a touch smaller, and let the rotation do the work.", "release"),
    (6, 3, "dev", "coach_nia", "squad", "routine", "boast", "technical",
     "follow_through", "shared",
     "Let the follow through go — you are cutting the swing off early and the ball "
     "dies before the side wall. More through the shot.", "release"),
    (6, 4, "dev", "self", "reflection", None, "boast", "technical", None, "shared",
     "stuart said smaller swing and nia said bigger follow through. i dont know "
     "which one to do so i just did what i normally do", "release"),
    (10, 2, "dev", "coach_nia", "squad", "block", "boast", "technical", None, "shared",
     "Still inconsistent on the boast. Hard to tell what you are going for."),

    # ---------------- Ellie: grip rebuild flagged mid competitive season
    (2, 1, "ellie", "coach_stuart", "lesson", None, "drive", "technical",
     "squeeze_grip", "shared",
     "Her grip is too far into the palm. It is costing her racket face control on "
     "everything. Proper fix is a rebuild, but she has states in six weeks — "
     "not touching it now. Logging it for the off-season.", "release"),
    (2, 1, "ellie", "coach_stuart", "lesson", None, "drive", "technical",
     None, "private",
     "Long term the grip has to change or she will plateau at this level. Needs a "
     "conversation with her and her parents about when, probably April."),
    (5, 3, "ellie", "coach_stuart", "squad", "pattern", "drive", "technical",
     "squeeze_grip", "shared",
     "Racket face opening on the backhand again under pace. Same root cause. We are "
     "working around it for now — aim higher and tighter instead.", "release"),
    (9, 2, "ellie", "coach_rob", "tournament", "match", "drive", "tactical",
     "aim_the_drive", "shared",
     "Won your group at the Philadelphia Open. Drives were a foot off the wall all "
     "day but you played the percentages and it held up.", "release"),
    (8, 3, "ellie", "coach_nia", "squad", "block", "drive", "technical",
     "squeeze_grip", "shared",
     "Blocked drives — the face still opens as soon as there is pace on the ball. It "
     "is the grip, same as always, and we are not changing that this term.", "release"),
    (11, 2, "ellie", "self", "reflection", None, "drive", "technical", None, "shared",
     "backhand still feels loose when they hit it hard at me. been like this all season", "release"),
    (11, 3, "ellie", "coach_stuart", "squad", "pattern", "drive", "technical",
     "squeeze_grip", "shared",
     # Written, not sent. The coach has not decided how to say this one yet.
     "Fourth time this block I have written the same thing about her grip. She is "
     "managing around it well and winning matches, but it is a ceiling."),

    # ---------------- Tomas: nine, short entries, age-appropriate
    # A coach note that is about managing the player, not coaching them. With
    # no rewrite to hide behind, this is where it belongs: coaches only.
    (1, 2, "tomas", "coach_nia", "squad", "block", "drive", "technical",
     "step_then_swing", "private",
     "Nine years old, first full block. Keep it to one thing at a time or he will "
     "lose both. Do not start on the grip this year."),
    (1, 2, "tomas", "coach_nia", "squad", "block", "drive", "technical",
     "step_then_swing", "shared",
     "Step, THEN hit. One big step before you swing. That's the only thing to "
     "remember today!", "release"),
    (1, 2, "tomas", "self", "reflection", None, "drive", "technical", None, "shared",
     "i did the stepping thing. it was fun", "release"),
    (5, 2, "tomas", "coach_nia", "squad", "block", "drive", "technical",
     "step_then_swing", "shared",
     "Stepping in now without being told. Big improvement in four weeks.", "release"),
    (5, 2, "tomas", "self", "reflection", None, "drive", "psychological", None, "shared",
     "i won a point against a big kid. i was really nervous at the start but i stopped "
     "being scared of him after that", "release"),
    (9, 2, "tomas", "coach_nia", "squad", "routine", "drive", "physical",
     "get_lower", "shared",
     "Ready for routines now. Next thing is getting lower — you are very upright.", "release"),

    # ---------------- Priya: private entries. These must never reach a coach agent.
    (4, 1, "priya", "coach_stuart", "lesson", None, "lob", "technical",
     "effect_on_ball", "shared",
     "Your lob is coming out flat and fast, so it isn't buying you the time you need. "
     "More height, and get under the ball. Small change, nothing drastic — this is "
     "your season.", "release"),
    (4, 2, "priya", "self", "reflection", None, "lob", "psychological", None, "private",
     "honestly i have been dreading squad all week. every session feels like a "
     "trial for college coaches and i cannot enjoy playing any more. i do not want "
     "stuart to know i feel like this"),
    (6, 3, "priya", "self", "reflection", None, "boast", "technical", None, "shared",
     "boast felt much better today, the rotation thing clicked", "release"),
    (8, 2, "priya", "self", "reflection", None, None, "psychological", None, "private",
     "did not sleep before the qualifier. kept thinking about messing up in front "
     "of the coach from Trinity"),
    (8, 4, "priya", "coach_rob", "tournament", "match", "lob", "tactical",
     None, "shared",
     "Semi-final at the qualifier, lost 3-2. Tactically excellent. You seemed tense "
     "between games — worth talking about when you want to.", "release"),
    (10, 1, "priya", "coach_stuart", "lesson", None, "lob", "technical",
     "effect_on_ball", "shared",
     "Height is better. Still quite flat when you are rushed.", "release"),

    # ---------------- Jonah: the control. Nothing is wrong here.
    (2, 2, "jonah", "coach_nia", "squad", "routine", "drive", "technical",
     "left_arm", "shared",
     "Left arm is doing nothing on the backhand. Use it as a counterbalance.", "release"),
    (6, 2, "jonah", "coach_nia", "squad", "pattern", "boast", "technical",
     "left_arm", "shared",
     "Left arm is in now and it has stuck in patterns too. Good four weeks.", "release"),
    (10, 3, "jonah", "coach_nia", "squad", "conditioned_game", "boast", "technical",
     None, "shared",
     "Holding up in conditioned games. Nothing to fix — time for harder drills.", "release"),
    (10, 4, "jonah", "self", "reflection", None, "boast", "tactical", None, "shared",
     "feeling good about my boast, want to try it more in matches", "release"),

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
        for pid, name in ADMINS:
            conn.execute(
                "INSERT INTO people (id, name, role, joined_on) VALUES (?,?,'admin',?)",
                (pid, name, BLOCK_START.isoformat()),
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

    _TERM = term_entries()
    for row in ENTRIES + _TERM:
        week_no, weekday, player, author, setting, rung, shot, category, cue, vis, text = row[:11]
        author_id = player if author == "self" else author
        # A coach note is released, or it is not. There is no second version:
        # the player reads what the coach wrote. Notes left unreleased stay
        # coach records, which is where anything not meant for a child goes.
        released = (author != "self" and len(row) > 11 and row[11] == "release")
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
            # Seeded rewrites stand for notes the coach already read and
            # released. A coach note with no rewrite stays unreleased, which
            # is what fills the approvals queue.
            approved_by=author_id if released else None,
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


# ---------------------------------------------------------------- the term
#
# The hand-written entries above are each player's storyline. This fills in
# the ordinary training around them so the record looks like a real term:
# squad most weekdays, a lesson a week, reflections when a player bothers,
# the odd solo session and a tournament weekend.
#
# No model calls, so density is free. Pools are written per player to
# reinforce that player's thread — Jonah stays clean, Ellie circles the grip,
# Maya keeps losing prep above the routine rung — and indexed so a line does
# not come back for several weeks.


# Seed-time cue tagging. In the running app the Organizer decides this; here
# the lines are ours, so the mapping is explicit rather than inferred, and the
# frequency counts the app reports are the ones the data was built to contain.
CUE_BY_PHRASE = [
    ("prep", "racket_before_feet"),
    ("racket is still coming up", "racket_before_feet"),
    ("stepping in", "step_then_swing"),
    ("step then swing", "step_then_swing"),
    ("sequence", "step_then_swing"),
    ("face opening", "squeeze_grip"),
    ("grip", "squeeze_grip"),
    ("left arm", "left_arm"),
    ("side wall under pressure", "responsible_pressure"),
    ("reached for the side wall", "responsible_pressure"),
    ("too safe", "responsible_pressure"),
    ("flat", "effect_on_ball"),
    ("cut", "effect_on_ball"),
    ("reaching rather than stepping", "step_then_swing"),
    ("controlled it from the t", "watch_them_hit"),
    ("length", "aim_the_drive"),
    ("tight and deliberate", "aim_the_drive"),
    ("soft hands", None),
    ("height", None),
]


def cue_for(text: str) -> str | None:
    low = text.lower()
    for phrase, cue in CUE_BY_PHRASE:
        if phrase in low:
            return cue
    return None


# (rung, text). "any" lines work in any theme week.
BANK: dict[str, dict] = {
    "maya": {"coach": "coach_stuart", "lesson_day": 0, "voice": [
        "prep felt fine today, nobody said anything about it",
        "good session. boast week is easier for me",
        "did 20 mins solo on the prep thing. feels stupid easy on my own",
        "late again in the game. i can feel it happening and still do it",
        "honestly getting bored of hearing about my racket",
        "really good drill today, the diagonals one",
        "tired. legs were heavy from the start",
        "won all my games in the sort which never happens",
    ], "any": [
        ("block", "Prep early and clean through the blocked work."),
        ("routine", "Routine held together. Prep good for the first half."),
        ("pattern", "Prep drifted late once the options opened up."),
        ("conditioned_game", "Prep gone in the game again — feet first."),
        ("routine", "Better. Prep held most of the routine today."),
        ("block", "No complaints in the blocks. You are clean when it is slow."),
        ("pattern", "Pattern work — prep fine until she had to choose, then late."),
        ("conditioned_game", "Conditioned game. Length good, prep late."),
    ], "drop": [
        ("block", "Drop blocks clean. Soft hands, good target."),
        ("conditioned_game", "Long/long/short. Drop fine, prep late into the front."),
    ], "lob": [
        ("routine", "Cross lob height good. Nothing on the side wall."),
        ("conditioned_game", "Reached for the side wall under pressure again."),
    ], "boast": [
        ("routine", "Boast is your best shot. Good cut, stays down."),
        ("pattern", "Boast held up in the pattern — you have more time on it."),
    ]},
    "dev": {"coach": "coach_nia", "lesson_day": 2, "voice": [
        "drops went well",
        "i dont really get the boast yet",
        "beat someone two courts up",
        "my arm was tired",
        "liked the dead quarters game",
        "i think im getting better at length",
    ], "any": [
        ("block", "Length improving. Still reaching rather than stepping in."),
        ("routine", "Routine was good for him. Clear sequence, stuck to it."),
        ("block", "Stepping in more today without being told."),
        ("routine", "Rushed the short ball every time it came up."),
        ("pattern", "First proper pattern. You took the options when they were there."),
        ("block", "Solid blocked session. You settle when you know what is coming."),
    ], "boast": [
        ("block", "Boast inconsistent. Hard to tell what shape you are going for."),
        ("routine", "Boast again — some good, some loose. Needs one clear idea of the swing."),
    ], "drop": [
        ("block", "Drop is your best shot. Genuinely soft hands."),
        ("routine", "Good drops. Confidence is up on this one."),
    ]},
    "ellie": {"coach": "coach_stuart", "lesson_day": 0, "voice": [
        "backhand loose again under pace",
        "good session, won most of my games",
        "states soon and i feel okay about it",
        "felt sharp today",
        "frustrated with the same thing every week",
        "long day. squash was the good bit",
    ], "any": [
        ("pattern", "Face opening under pace on the backhand. We are managing around it."),
        ("conditioned_game", "Percentages held all session. Drives a foot off the wall."),
        ("routine", "Clean routine. Most consistent in the squad."),
        ("pattern", "Same grip issue showing under pace. Aiming higher to compensate."),
        ("conditioned_game", "Controlled the game. Tactically very mature."),
        ("routine", "Good session. Nothing new."),
    ], "drive": [
        ("pattern", "Backhand face opening again under pace. Known problem."),
        ("conditioned_game", "Two-bounce length game. Held up on percentages."),
    ], "lob": [
        ("routine", "Lob is reliable. One of the better ones here."),
    ]},
    "tomas": {"coach": "coach_nia", "lesson_day": 2, "voice": [
        "squash was fun",
        "i did 50 in a row",
        "i like lob week",
        "my legs hurt after",
        "i hit one in the nick",
        "i want to play a tournament",
    ], "any": [
        ("block", "Stepping in on most of them now. Big progress."),
        ("block", "Step then swing is becoming automatic."),
        ("block", "Good blocked session. One cue at a time still."),
        ("routine", "First routines. Managing the sequence, losing the technique."),
        ("block", "Back to blocks today — routines were a stretch last week."),
        ("routine", "Routine went better. Sequence and technique both holding."),
    ], "lob": [
        ("block", "Lob is a good shot for him. Gets height easily."),
    ], "drop": [
        ("block", "Drops are hard at nine. We will keep it simple for now."),
    ]},
    "priya": {"coach": "coach_stuart", "lesson_day": 0, "voice": [
        "felt in control today",
        "lob still flat when im rushed",
        "tired this week",
        "good session",
        "thinking a lot about next year",
        "best ive hit it in a while",
    ], "any": [
        ("pattern", "Drives tight and deliberate. Really mature shot choice."),
        ("conditioned_game", "You controlled it from the T throughout."),
        ("routine", "Clean session. Nothing to fix technically."),
        ("pattern", "Occasionally too safe when you could attack."),
        ("conditioned_game", "Read the game well. Good decisions under pressure."),
        ("routine", "Solid. A bit quiet today though."),
    ], "lob": [
        ("routine", "Lob still coming out flat and quick whenever you are rushed."),
        ("pattern", "Lob height better in the routine, flat again in the pattern."),
    ], "boast": [
        ("routine", "Boast rotation clicked this week. Much better."),
    ]},
    "jonah": {"coach": "coach_nia", "lesson_day": 2, "voice": [
        "good week",
        "want to play more matches",
        "enjoyed the conditioned games",
        "felt strong today",
        "the left arm thing is automatic now",
    ], "any": [
        ("routine", "Clean. Left arm is doing its job."),
        ("pattern", "Held up well in the pattern. Nothing to fix."),
        ("conditioned_game", "Used it well in the game without forcing it."),
        ("routine", "Steady improvement. Ready for harder constraints."),
        ("pattern", "Good decisions. You read the game really well."),
        ("conditioned_game", "You look comfortable at this level now."),
    ], "boast": [
        ("routine", "Boast is good. Ready for more difficult versions."),
    ]},
}


# How each player moves up the ladder over the twelve weeks. This is the whole
# point of the dataset: a cue that is still being raised at the same rung in
# October as in August has not been learned, and one that has climbed has.
# Rung comes from here, not from the text pool, so the trend is a property of
# the player's story rather than an artefact of list order.
TRAJECTORY = {
    # climbing: block -> routine -> pattern -> conditioned game
    "jonah":  ["block", "block", "routine", "routine", "routine", "pattern",
               "pattern", "pattern", "conditioned_game", "conditioned_game",
               "conditioned_game", "conditioned_game"],
    "tomas":  ["block", "block", "block", "block", "block", "routine",
               "routine", "routine", "routine", "routine", "pattern", "pattern"],
    "dev":    ["block", "block", "block", "routine", "routine", "routine",
               "routine", "pattern", "routine", "pattern", "pattern", "pattern"],
    # stuck: gets to pattern and falls back every time the shot comes round
    "maya":   ["block", "routine", "pattern", "block", "routine", "pattern",
               "block", "routine", "pattern", "block", "routine", "pattern"],
    # managed, not fixed: high rungs throughout, no movement
    "ellie":  ["pattern", "conditioned_game", "pattern", "pattern",
               "conditioned_game", "pattern", "conditioned_game", "pattern",
               "pattern", "conditioned_game", "pattern", "conditioned_game"],
    "priya":  ["routine", "pattern", "pattern", "conditioned_game", "pattern",
               "conditioned_game", "pattern", "conditioned_game",
               "conditioned_game", "pattern", "conditioned_game", "pattern"],
}

# Mon-Fri. Squad most days; one lesson a week; Friday is often solo.
SQUAD_DAYS = (0, 1, 3, 4)


def term_entries() -> list[tuple]:
    """A coach note most training days, a lesson a week, reflections throughout."""
    out: list[tuple] = []
    for week_no in range(1, 13):
        shot = ROTATION[(week_no - 1) % 4]
        for pid, bank in BANK.items():
            coach = bank["coach"]
            pool = bank.get(shot, []) + bank["any"]
            step = 0

            week_rung = TRAJECTORY[pid][week_no - 1]
            for weekday in SQUAD_DAYS:
                if weekday == bank["lesson_day"]:
                    continue
                _pool_rung, text = pool[(week_no * 3 + step) % len(pool)]
                # The week itself climbs: constrained early, open by Thursday.
                rung = week_rung
                if weekday <= 1:
                    rung = db.RUNGS[max(0, db.RUNGS.index(week_rung) - 1)]
                out.append((week_no, weekday, pid, coach, "squad", rung, shot,
                            "technical", cue_for(text), "shared", text, "release"))
                step += 1

            lesson_rung, lesson_text = pool[(week_no * 5) % len(pool)]
            out.append((week_no, bank["lesson_day"], pid, coach, "lesson", None, shot,
                        "technical", cue_for(lesson_text), "shared",
                        f"Lesson. {lesson_text}", "release"))

            voice = bank["voice"]
            # A reflection on the lesson day itself, most weeks. The lesson is
            # where a player has something to react to, so this is where the
            # two accounts of one session actually pair up.
            if week_no % 3 != 0:
                out.append((week_no, bank["lesson_day"], pid, "self", "reflection",
                            None, shot, "technical",
                            cue_for(voice[week_no % len(voice)]), "shared",
                            voice[week_no % len(voice)]))
            for n, weekday in enumerate((1, 4)):
                if (week_no + n) % 2:
                    continue
                line = voice[(week_no + n) % len(voice)]
                out.append((week_no, weekday, pid, "self", "reflection", None, shot,
                            "technical", cue_for(line), "shared", line))

            if week_no % 4 == 0:
                out.append((week_no, 4, pid, coach, "solo", "solo", shot,
                            "technical", None, "shared",
                            f"Solo assigned: {shot} work, 20 minutes.", "release"))
    return out
