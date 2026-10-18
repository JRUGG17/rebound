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

    # ---------------- Week 11, this week: what the squad is actually on.
    # Several players on the same cue is normal, and it is the whole point of
    # the squad card — the coach has two minutes on the bleachers and should
    # lead with whatever most of the group is working on.
    (11, 2, "priya", "coach_nia", "squad", "block", "drop", "technical",
     "racket_before_feet", "shared",
     "Prep is late on the drop when she is moving forward. Same note as half the group "
     "this week."),
    (11, 2, "jonah", "coach_nia", "squad", "block", "drop", "technical",
     "racket_before_feet", "shared",
     "Racket coming up after the first step rather than before it. Worth a group cue."),
    (11, 3, "tomas", "coach_nia", "squad", "routine", "drop", "physical",
     "get_lower", "shared",
     "Very upright into the front corners. Needs to soften the knees."),
    (11, 3, "dev", "coach_nia", "squad", "routine", "drop", "physical",
     "get_lower", "shared",
     "Standing tall on the drop, so he is reaching rather than stepping in."),

    # ---------------- Dev: two coaches, opposite advice, same week
    (6, 1, "dev", "coach_stuart", "lesson", None, "boast", "technical",
     "follow_through", "shared",
     "Boast swing is loose and flappy — too much arm, no shape. Bring it back toward "
     "a drive swing, maybe a touch smaller, and let the rotation do the work."),
    (6, 3, "dev", "coach_nia", "squad", "routine", "boast", "technical",
     "follow_through", "shared",
     "Told him to let the follow through go — he is cutting the swing off early and "
     "the ball dies before the side wall. Needs more through the shot."),
    (6, 4, "dev", "self", "reflection", None, "boast", "technical", None, "shared",
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
     "i won a point against a big kid. i was really nervous at the start but i stopped "
     "being scared of him after that"),
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
    (10, 4, "jonah", "self", "reflection", None, "boast", "tactical", None, "shared",
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
        player_text = (row[11] if len(row) > 11
                       else (player_text_for(text) if author != "self" else None))
        # Generated term notes are already written to the player, so they ship
        # as the coach wrote them. The hand-written storyline notes are not,
        # and keep their separate player version or stay unreleased.
        if player_text is None and author != "self" and row in _TERM:
            player_text = text
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
            player_text=player_text,
            # Seeded rewrites stand for notes the coach already read and
            # released. A coach note with no rewrite stays unreleased, which
            # is what fills the approvals queue.
            approved_by=author_id if player_text else None,
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


# Kid-facing versions of the seeded coach notes, keyed by a snippet of the
# original. In the running app the Organizer drafts these and the coach edits
# and releases them; here they stand for notes already released, so a player's
# journal has history in it. Keys must stay unique within the seed.
PLAYER_TEXTS = {
    "Blocked drop work": "Your prep was early and clean the whole way through the "
        "blocked drops today. That's exactly it.",
    "Long/long/short with dead quarters": "In the game your prep went back to late — "
        "feet first most rallies. It held up in the blocked work, so the question is "
        "what changes once you're choosing where to hit.",
    "Back to racket before feet": "We're back on racket before feet. It's there when "
        "you're thinking about it and gone when you're not, so let's make it automatic.",
    "Drive/drop strict pattern": "Prep held for the first few in the pattern, then "
        "started drifting late. Longer than last time though.",
    "Third Drop Week running": "This is the third Drop Week we've worked on racket "
        "before feet. That tells me something else is going on underneath it, so let's "
        "look at when you're picking the ball up rather than just the prep itself.",
    "Cross lob blocks": "Your cross lob in the blocks was textbook — good height, "
        "nothing touching the side wall.",
    "Drive/boast/cross-lob routine": "Lob still holding up well in the routine, "
        "diagonals included.",
    "Went for the side wall under pressure": "Under pressure you went for the side wall "
        "three times and two went out. When you're stretched, take the back wall on the "
        "fly instead — that's what the lob is for.",
    "Lost 3-1 at the Mid-Atlantic": "Tough one. The pattern was the same as in training: "
        "every reset went for the nick and you couldn't get out of the back. Good thing "
        "to work on next.",
    "Boast swing is loose and flappy": "Your boast swing is getting loose — too much "
        "arm and not much shape. Build it like a drive swing, maybe a touch smaller, "
        "and let your body rotation do the work.",
    "Told him to let the follow through go": "You're cutting the swing off early, so the "
        "ball dies before it reaches the side wall. Let the follow through go through "
        "the shot.",
    "Stepping in now without being told": "You're stepping in now without me saying it. "
        "That's a big improvement in four weeks.",
    "Ready for routines now": "You're ready for routines. Next thing is getting lower — "
        "soften the knees, get your hand closer to the floor.",
    "Prep is late on the drop": "Your prep is late on the drop when you're moving "
        "forward. Racket up before you move.",
    "Racket coming up after the first step": "Your racket is coming up after the first "
        "step. Try to get it up before you move.",
    "Very upright into the front corners": "You're staying quite tall into the front "
        "corners. Soften the knees and get down to the ball.",
    "Standing tall on the drop": "You're standing tall on the drop, so you're reaching "
        "for it instead of stepping in. Get lower and step.",
    "Left arm doing nothing": "Your left arm isn't doing anything on the backhand — use "
        "it as a counterbalance.",
    "Left arm is in now": "Left arm is in now, and it's stuck in the patterns too. "
        "Really good four weeks.",
    "Holding up in conditioned games": "Boast is holding up in conditioned games. "
        "Nothing to fix — time for harder drills.",
    "Height is better": "Lob height is better. Still comes out flat when you're rushed, "
        "so that's the next bit.",
    "Semi-final at the qualifier": "Really tight semi-final. Tactically that was some of "
        "your best squash.",
    "Won her group at the Philadelphia Open": "Won your group. Drives were a foot off the "
        "wall all day but you played the percentages and it held up.",
    "Blocked drives — the face is still opening": "The racket face is still opening up as "
        "soon as there's pace on the ball. We're working around it this term rather than "
        "changing anything mid-season.",
    "Fourth time this block": "Same note as the last few times on your grip. You're "
        "managing around it really well and winning matches — we'll do the proper fix in "
        "the spring, not now.",
}


def player_text_for(raw: str) -> str | None:
    for key, text in PLAYER_TEXTS.items():
        if key in raw:
            return text
    return None


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
                            "technical", cue_for(text), "shared", text))
                step += 1

            lesson_rung, lesson_text = pool[(week_no * 5) % len(pool)]
            out.append((week_no, bank["lesson_day"], pid, coach, "lesson", None, shot,
                        "technical", cue_for(lesson_text), "shared",
                        f"Lesson. {lesson_text}"))

            voice = bank["voice"]
            for n, weekday in enumerate((1, 4)):
                if (week_no + n) % 2:
                    continue
                line = voice[(week_no + n) % len(voice)]
                out.append((week_no, weekday, pid, "self", "reflection", None, shot,
                            "technical", cue_for(line), "shared", line))

            if week_no % 4 == 0:
                out.append((week_no, 4, pid, coach, "solo", "solo", shot,
                            "technical", None, "shared",
                            f"Solo assigned: {shot} work, 20 minutes."))
    return out
