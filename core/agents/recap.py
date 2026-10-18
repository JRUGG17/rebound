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


class Bucket(BaseModel):
    category: Category
    headline: str = Field(
        description="One sentence on what happened in this area. Concrete — name the "
        "shot, the rung, the cue. If there is nothing in this bucket, say what that "
        "absence means rather than inventing content."
    )
    standout: str | None = Field(
        default=None,
        description="The single thing most worth noticing here, if there is one.",
    )


class Recap(BaseModel):
    overview: str = Field(
        description="Two sentences. What this stretch of time actually looked like. "
        "Use only counts that appear in the digest."
    )
    emphasis: Category | None = Field(
        default=None, description="Which trainable dominated, if one did."
    )
    buckets: list[Bucket] = Field(
        description="One per trainable that has anything in it, in order of weight."
    )
    recurring: list[str] = Field(
        default_factory=list,
        description="Things that came back more than once, with their exact counts from "
        "the digest. This is the most valuable part — it is what a diary normally hides.",
    )
    gap: str | None = Field(
        default=None,
        description="Set when a trainable has nothing recorded at all and that absence "
        "is worth naming. Not an accusation, just a fact worth seeing.",
    )


PLAYER_INSTRUCTIONS = """
You are writing a player's own recap of their training over a stretch of time.
They are between 8 and 18. Match the language to their age.

This is their record, so write to them, about what they did. Be honest about
what kept coming back, because that is the whole point — but it is a summary,
not a telling-off, and not a pep talk either.

You do not coach. You do not suggest fixes or drills. You say what happened
and what kept happening.
"""

COACH_INSTRUCTIONS = """
You are writing a coach's recap of one player over a stretch of time. Terse
and specific. Lead with the shape of it, name the shot and the rung, and do
not pad.

You do not prescribe. The coach decides what to do about it.
"""


async def recap_period(player_id: str, start: str, end: str,
                       *, audience: Audience = "player"):
    stats = analysis.period_stats(
        player_id, start, end, viewer="player" if audience == "player" else "coach")
    if not stats["total"]:
        return None, None

    instructions = PLAYER_INSTRUCTIONS if audience == "player" else COACH_INSTRUCTIONS
    agent = make_agent(instructions, Recap)
    prompt = (
        f"{analysis.period_digest(stats)}\n\n"
        "Every number above is counted, not estimated. Do not state a count that is "
        "not in it, and do not round one that is.\n"
        "Write the recap."
    )
    output, usage = await run(agent, prompt, name=f"recap:{audience}")
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

    agent = make_agent(DAY_INSTRUCTIONS, DaySummary)
    prompt = (
        f"{analysis.period_digest(stats)}\n\n"
        f"FOR CONTEXT — what has been recurring over the whole record:\n{context}\n\n"
        f"Summarise {day}."
    )
    return await run(agent, prompt, name=f"day:{audience}")
