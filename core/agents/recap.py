"""The Recap agent — a week or a month, structured.

The failure this exists to prevent is the one the author's own training diary
fell into: years of notes that were individually fine and collectively
unreadable, because nothing ever grouped them. An info dump with better
grammar is not an improvement.

So the output is structured, not prose. Four buckets, one per trainable, each
with a count that came from SQL and a headline that came from the model. The
reader sees the shape first — "eleven entries, mostly technical, nothing
physical at all" — and opens a bucket only if they want the detail.

All arithmetic arrives pre-computed in the digest. The model is told never to
state a number that is not in it, because a recap that miscounts is worse
than no recap: a player will believe it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core import analysis
from core.agents.base import make_agent, run

Category = Literal["technical", "tactical", "physical", "psychological"]
Audience = Literal["player", "coach"]


Direction = Literal["climbing", "flat", "slipping", "new", "unclear"]


class Theme(BaseModel):
    """One big idea, drawn from many entries."""

    title: str = Field(
        description="The idea in four or five words, as a coach would say it. "
        "Not a date, not a session, not a quote."
    )
    category: Category
    cue_id: str | None = Field(
        default=None,
        description="The canonical cue id from the digest if this theme is one, so the "
        "reader can open the entries behind it. Null if it spans several or none.",
    )
    direction: Direction = Field(
        description="Use the ladder trend in the digest. Climbing means it is being "
        "worked at higher rungs than it was. Flat means it keeps coming back at the "
        "same level. New means it only started this period."
    )
    what_it_is: str = Field(
        description="Two or three sentences pulling together everything that belongs to "
        "this theme. Synthesise it — do not list sessions, do not recount days one by "
        "one, and do not quote entries verbatim. The reader can open the detail if they "
        "want it; this is the version that saves them having to. Say where each claim "
        "comes from: what the coaches wrote, and separately what the player wrote. "
        "Never present the player's own words back to them as an observation about them."
    )
    evidence: str = Field(
        description="The counts behind it, taken exactly from the digest. "
        "For example: 13 mentions this period, 44 all term, ladder +0.28."
    )


class Recap(BaseModel):
    overview: str = Field(
        description="Two sentences. What this stretch of time actually looked like. "
        "Use only counts that appear in the digest."
    )
    emphasis: Category | None = Field(
        default=None, description="Which trainable dominated, if one did."
    )
    themes: list[Theme] = Field(
        description="Two to four. The big ideas of this period, most important first. "
        "A theme is something that runs across many entries, not a single session. "
        "Fewer and better beats a list of everything that happened."
    )
    headline: str = Field(
        description="The single most important thing about this period, in one short "
        "sentence. If one thing dominates, say it plainly."
    )
    gap: str | None = Field(
        default=None,
        description="Set when a trainable has nothing recorded at all and that absence "
        "is worth naming. Not an accusation, just a fact worth seeing.",
    )


PLAYER_INSTRUCTIONS = """
You are writing a player's own recap of their training over a stretch of time.
They are between 8 and 18. Match the language to their age.

AMALGAMATE. You are given dozens of entries and you are not summarising them
one by one — you are finding the two to four ideas that run through them and
writing those. "On the 12th you did X, on the 14th you did Y" is the thing
this page exists to replace. A reader who wants the days can open them.

Use the ladder trend to say which way something is going. A cue being worked
at higher rungs than it was is going somewhere. One still being raised at the
same rung after two months is not, and saying so plainly is the most useful
thing on the page.

This is their record, so write to them. Honest, not a telling-off and not a
pep talk. You do not coach and you do not suggest drills.

ATTRIBUTE EVERYTHING. The digest marks each entry (coach) or (player). Those
are different kinds of claim and must never be blended into one voice. You
are writing to a coach about somebody else's record, so "you" is the coach
reading it and never the player:

  a coach's note      -> "Nia wrote...", "two coaches noted..."
  the player's own    -> "Maya wrote that...", "she said it felt..."

Use the player's name from the digest. "You wrote" about a note the player
wrote tells the coach they wrote something they did not.

Never state a player's own reflection back as though it were a
finding about them. "Hearing about your racket was getting frustrating" is
the app telling a child how they feel. "You wrote twice that you were bored
of hearing about your racket" is reporting what they said. The second is
true, the first is presumptuous, and the difference is one clause.

Where a coach's view and the player's own view disagree, that is worth a
sentence of its own — say both and whose each is.
"""

COACH_INSTRUCTIONS = """
You are writing a coach's recap of one player over a stretch of time. Terse
and specific.

AMALGAMATE. Two to four themes across the whole period, not a session list.
Name the shot, the rung, the direction. Use the ladder trend: a cue still
being raised at the same rung after two months has not been learned, and
that is the sentence a coach needs.

You do not prescribe. The coach decides what to do about it.

ATTRIBUTE EVERYTHING. The digest marks each entry (coach) or (player). Those
are different kinds of claim and must never be blended into one voice. You
are writing to a coach about somebody else's record, so "you" is the coach
reading it and never the player:

  a coach's note      -> "Nia wrote...", "two coaches noted..."
  the player's own    -> "Maya wrote that...", "she said it felt..."

Use the player's name from the digest. "You wrote" about a note the player
wrote tells the coach they wrote something they did not.

Never state a player's own reflection back as though it were a
finding about them. "Hearing about your racket was getting frustrating" is
the app telling a child how they feel. "You wrote twice that you were bored
of hearing about your racket" is reporting what they said. The second is
true, the first is presumptuous, and the difference is one clause.

Where a coach's view and the player's own view disagree, that is worth a
sentence of its own — say both and whose each is.
"""


async def recap_period(player_id: str, start: str, end: str,
                       *, audience: Audience = "player", force: bool = False,
                       setting: str | None = None, author: str | None = None):
    """A recap of one stretch of time. Written once, then kept.

    Re-reading an unchanged September costs exactly what reading it the first
    time cost and returns the same thing, so it is not re-read. The stored
    copy is invalidated by the entry count changing, which is what happens
    when somebody adds to the period.
    """
    from core import db

    stats = analysis.period_stats(
        player_id, start, end, viewer="player" if audience == "player" else "coach",
        setting=setting, author=author)
    if not stats["total"]:
        return None, None

    # A filtered recap is a different summary of a different set, so it gets
    # its own cache slot rather than overwriting the unfiltered one.
    kind = "recap" + (f":{setting or 'all'}:{author or 'all'}"
                      if (setting or author) else "")
    if not force:
        hit = db.get_summary(player_id, kind, audience, start, end, stats["total"])
        if hit:
            return Recap.model_validate(hit["payload"]), hit

    instructions = PLAYER_INSTRUCTIONS if audience == "player" else COACH_INSTRUCTIONS
    agent = make_agent(instructions, Recap)
    prompt = (
        f"{analysis.period_digest(stats)}\n\n"
        "Every number above is counted, not estimated. Do not state a count that is "
        "not in it, and do not round one that is.\n"
        "Write the recap."
    )
    output, usage = await run(agent, prompt, name=f"recap:{audience}")
    db.put_summary(player_id, kind, audience, start, end,
                   output.model_dump(), stats["total"], usage)
    return output, usage


class DaySummary(BaseModel):
    what_happened: str = Field(
        description="One or two sentences on what this day actually was. Plain, not "
        "dramatic. If it was an ordinary session, say so."
    )
    fits_in: str | None = Field(
        default=None,
        description="How this day sits against the longer picture — whether it is the "
        "same thing coming back again, the first time something has held, or a break "
        "from the pattern. Null if there is nothing meaningful to connect it to.",
    )


DAY_INSTRUCTIONS = """
You are summarising a single day in a player's training record, for them to
read. One or two sentences on the day, then at most one sentence on how it
fits the longer run.

Most days are ordinary. Say so when they are — inflating a normal session
into a milestone makes the whole record untrustworthy, and a player will
stop reading it.

You do not coach and you do not give advice.
"""


async def summarise_day(player_id: str, day: str, *, audience: Audience = "player"):
    from core import db

    viewer = "player" if audience == "player" else "coach"
    stats = analysis.period_stats(player_id, day, day, viewer=viewer)
    if not stats["total"]:
        return None, None

    # The longer view, so "fits_in" has something to be measured against.
    runs = [r for r in analysis.cue_runs(player_id) if r.count > 1]
    context = "\n".join(
        f"  {r.canonical}: {r.count} times across weeks "
        f"{sorted(set(r.weeks))}{'  <-- chronic' if r.is_chronic else ''}"
        for r in runs) or "  nothing has recurred yet"

    hit = db.get_summary(player_id, "day", audience, day, day, stats["total"])
    if hit:
        return DaySummary.model_validate(hit["payload"]), hit

    agent = make_agent(DAY_INSTRUCTIONS, DaySummary)
    prompt = (
        f"{analysis.period_digest(stats)}\n\n"
        f"FOR CONTEXT — what has been recurring over the whole record:\n{context}\n\n"
        f"Summarise {day}."
    )
    output, usage = await run(agent, prompt, name=f"day:{audience}")
    db.put_summary(player_id, "day", audience, day, day,
                   output.model_dump(), stats["total"], usage)
    return output, usage


class Phase(BaseModel):
    """A stretch of lessons spent on one thing."""

    span: str = Field(description="The dates it ran between, from the digest.")
    focus: str = Field(description="What the lessons were about, in a few words.")
    what_happened: str = Field(
        description="One or two sentences. Did it move? Say which way, using the "
        "lessons themselves. Attribute: what the coach wrote, what the player wrote."
    )


class LessonArc(BaseModel):
    overview: str = Field(
        description="Two or three sentences on the shape of the lesson thread as a "
        "whole. Counts only from the digest."
    )
    phases: list[Phase] = Field(
        description="The focus eras in order, oldest first. Two to four. A phase is a "
        "stretch of lessons on one thing, not one lesson."
    )
    carried_over: list[str] = Field(
        default_factory=list,
        description="Things raised in a lesson that came back in a later lesson still "
        "unresolved, with how many lessons apart. This is what the thread is for.",
    )
    never_answered: list[str] = Field(
        default_factory=list,
        description="Questions or worries the player raised in a lesson that no later "
        "lesson picks up. Empty if none — do not manufacture them.",
    )


LESSON_INSTRUCTIONS = """
You are reading a player's private lessons end to end — the place their
technical focus gets set — and describing how that thread has gone.

A lesson is not a session. Group them into the two to four things the term
was actually about, and say whether each moved.

Attribute everything. The digest marks each entry (coach) or (player). Those
are different claims and a lesson thread is exactly where the gap between
them shows, so never blend them into one voice.

{voice}

What earns its place here is continuity: something raised in August that is
still being raised in October, or a worry the player voiced that no later
lesson answers. Do not manufacture either. If the thread is healthy, say so.

You do not coach and you do not prescribe drills.
"""


LESSON_VOICE_PLAYER = """This is the player's own record, so write to them:
  a coach's note    -> "your coach wrote...", "Nia noticed..."
  their own         -> "you wrote that...", "you said it felt..."
"""

LESSON_VOICE_COACH = """You are writing to a coach about somebody else's
record, so "you" is the coach reading it and never the player:
  a coach's note    -> "Nia wrote...", "two coaches noted..."
  {name}'s own      -> "{name} wrote that...", "{name} said it felt..."
"""


async def recap_lessons(player_id: str, *, audience: Audience = "player",
                        start: str | None = None, end: str | None = None,
                        force: bool = False):
    from core import db

    viewer = "player" if audience == "player" else "coach"
    items = analysis.lessons(player_id, viewer=viewer)
    if start:
        items = [i for i in items if i["on"] >= start]
    if end:
        items = [i for i in items if i["on"] <= end]
    if not items:
        return None, None

    # The cache key is the span of what was actually read, so each range
    # gets its own slot without a flag saying which range it was.
    span = (items[-1]["on"], items[0]["on"])
    total = sum(len(i["coach"]) + len(i["player"]) for i in items)
    if not force:
        hit = db.get_summary(player_id, "lessons", audience, span[0], span[1], total)
        if hit:
            return LessonArc.model_validate(hit["payload"]), hit

    player = db.person(player_id)
    lines = [f"PLAYER: {player['name']}, age {player['age']}",
             f"LESSONS ON RECORD: {len(items)}, "
             f"{items[-1]['on']} to {items[0]['on']}", ""]
    for lesson in reversed(items):
        week = lesson["week"]
        theme = f" · {week['theme_name']}" if week else ""
        lines.append(f"--- {lesson['on']}{theme}")
        for entry in lesson["coach"]:
            lines.append(f"  (coach {db.person(entry['author_id'])['name']}) "
                         f"{analysis._clip(db.agent_text(entry), 180)}")
        for entry in lesson["player"]:
            lines.append(f"  (player) {analysis._clip(db.agent_text(entry), 180)}")

    # The same thread, told to two different readers. A coach reading
    # "your coach wrote" about a note they wrote themselves is the version
    # of this that was shipped first.
    voice = LESSON_VOICE_PLAYER if audience == "player" else (
        LESSON_VOICE_COACH.format(name=player["name"].split()[0]))
    agent = make_agent(LESSON_INSTRUCTIONS.format(voice=voice), LessonArc)
    output, usage = await run(agent, "\n".join(lines) + "\n\nRead this thread.",
                              name=f"lessons:{audience}")
    db.put_summary(player_id, "lessons", audience, span[0], span[1],
                   output.model_dump(), total, usage)
    return output, usage


# ---------------------------------------------------------------- the month

class MonthNote(BaseModel):
    """One thing worth saying about a month, with the detail to back it."""

    headline: str = Field(
        description="The point in six or seven words, as a coach would say it out "
        "loud. Not a date and not a quote."
    )
    detail: str = Field(
        description="Three or four full sentences. This is the part that gets read, "
        "so write it properly rather than gesturing at it. Say what happened, where "
        "it showed up — which settings, which rungs of the ladder, early or late in "
        "the month — and what changed across the weeks if anything did. Attribute "
        "every claim: what the coaches wrote is one kind of statement and what the "
        "player wrote is another, and they must never be blended. Synthesise across "
        "entries rather than recounting sessions one by one, and do not quote "
        "entries verbatim."
    )
    category: Category
    evidence: str = Field(
        description="The counts behind it, taken exactly from the digest. For "
        "example: 7 entries, 3 sessions, 2 coaches."
    )


class MonthReview(BaseModel):
    """One month, in a fixed shape, so two months can be compared."""

    overview: str = Field(
        description="Four or five sentences on the month as a whole. What it was "
        "mostly about, how it opened and how it ended, and whether it looks like a "
        "month where things moved. Use only counts that appear in the digest. Write "
        "it as a paragraph somebody would actually read, not a summary line."
    )
    going_well: list[MonthNote] = Field(
        default_factory=list,
        description="One to three. Things that are working — a shot holding up, a "
        "cue that has climbed the ladder, something the player has got on top of. "
        "Real ones only. If the month was a grind, say so in the overview and leave "
        "this short rather than inventing encouragement.",
    )
    working_on: list[MonthNote] = Field(
        default_factory=list,
        description="One to three. The live problems of the month: what is being "
        "worked at and has not landed yet. Not a telling-off and not a prescription "
        "— describe the state of it, do not say what to do about it.",
    )
    kept_coming_back: list[MonthNote] = Field(
        default_factory=list,
        description="Things that recurred often enough in this month to be a pattern "
        "rather than an incident, using the recurrence counts in the digest. Empty "
        "if nothing did — do not pad it.",
    )
    quiet: str | None = Field(
        default=None,
        description="One sentence naming any trainable with nothing recorded at all "
        "this month. A fact worth seeing, not an accusation. Null if all four have "
        "something.",
    )


MONTH_PLAYER = """
You are writing one month of a player's training record back to them. They are
between 8 and 18 — match the language to their age.

This page is the month. It is the thing they will look at to remember what
September was, so it has to stand on its own and it has to be worth the visit.
Write in full sentences and give each note enough substance that reading it
tells them something. A page of four-word fragments is a worse page.

AMALGAMATE. You are given every entry; you are not summarising them one at a
time. Find what ran through the month and write that.

ATTRIBUTE EVERYTHING. The digest marks each entry (coach) or (player):
  a coach's note    -> "your coaches wrote...", "Nia noticed..."
  their own         -> "you wrote that...", "you said it felt..."
Never hand a player their own reflection back as a finding about them.

Use the ladder trend to say which way something went. You do not coach, you do
not prescribe drills, and you do not tell them what to do next month.
"""

MONTH_COACH = """
You are writing one month of a player's record for a coach. Terse where terse
is right, but complete: this is a page a coach reads before a session, and
each note should carry enough detail to act on without opening the entries.

AMALGAMATE into the shape of the month — settings, rungs, what moved. Name the
shot and the rung. Use the ladder trend: a cue still being raised at the same
rung after a month has not been learned.

ATTRIBUTE EVERYTHING. You are writing to a coach about somebody else's record,
so "you" is the coach reading it and never the player. Use the player's name
from the digest:
  a coach's note    -> "Nia wrote...", "two coaches noted..."
  the player's own  -> "Maya wrote that...", "she said it felt..."

You do not prescribe. The coach decides what to do about it.
"""


async def review_month(player_id: str, month: str, *,
                       audience: Audience = "player", force: bool = False):
    """One calendar month, in a fixed shape.

    The period recap returns whatever two-to-four themes the model finds, which
    reads well and makes two months impossible to lay side by side. This has
    the same skeleton every time — going well, working on, kept coming back —
    so September and October can be compared at a glance, and the curriculum's
    four trainables stay visible rather than being implied.

    `month` is "YYYY-MM". Cached on the month and its entry count, so looking
    at September twice costs one call, and a new September entry invalidates it.
    """
    from datetime import date
    from calendar import monthrange
    from core import clock, db

    year, mon = int(month[:4]), int(month[5:7])
    start = date(year, mon, 1).isoformat()
    end = min(date(year, mon, monthrange(year, mon)[1]).isoformat(),
              clock.today().isoformat())
    if end < start:
        return None, None

    viewer = "player" if audience == "player" else "coach"
    stats = analysis.period_stats(player_id, start, end, viewer=viewer)
    if not stats["total"]:
        return None, None

    if not force:
        hit = db.get_summary(player_id, f"month:{month}", audience,
                             start, end, stats["total"])
        if hit:
            return MonthReview.model_validate(hit["payload"]), hit

    instructions = MONTH_PLAYER if audience == "player" else MONTH_COACH
    agent = make_agent(instructions, MonthReview)
    label = date(year, mon, 1).strftime("%B %Y")
    prompt = (
        f"{analysis.period_digest(stats)}\n\n"
        f"This is {label}, read as one month.\n"
        "Every number above is counted, not estimated. Do not state a count that "
        "is not in it, and do not round one that is.\n"
        "Write the month."
    )
    output, usage = await run(agent, prompt, name=f"month:{audience}")
    db.put_summary(player_id, f"month:{month}", audience, start, end,
                   output.model_dump(), stats["total"], usage)
    return output, usage
