"""The Comparison agent.

The one that does something no coach currently can, because no coach sees all
of it. It reads a digest of counted facts (see core/analysis.py) and names
what is actually going on:

  transfer gap    a shot that holds at block and routine and dies above them.
                  The rung where it stops is the finding.
  chronic cue     the same cue back across three theme weeks. On a four-week
                  rotation that is twelve weeks of one unresolved problem, and
                  at that point it is not a reminder, it is a blocker.
  conflict        two coaches telling one child opposite things.
  blind spot      what the player thinks they are working on versus what the
                  coaches have been writing.

It does not prescribe fixes — that is coaching, and agents do not coach. It
says what the pattern is and hands it to a coach. It is also required to
respect the time of year: a technical rebuild flagged during a competitive
block is noted for the off-season, not pushed as urgent.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core import analysis, clock, db
from core.agents.base import make_agent, run

Rung = Literal["solo", "block", "routine", "pattern", "conditioned_game", "match"]

FindingKind = Literal[
    "transfer_gap", "chronic_cue", "coach_conflict", "blind_spot", "progress"
]


class Finding(BaseModel):
    kind: FindingKind
    headline: str = Field(
        description="One sentence a coach could read in four seconds. Name the shot and "
        "the rung where it breaks, or the cue and how long it has been back."
    )
    evidence: str = Field(
        description="The specific entries this rests on, with their counts and weeks. "
        "Use the numbers from the digest exactly — never round or estimate them."
    )
    # A Literal, not a str. The model returned "conditioned game" with a space
    # and the finding read fine to a human while failing every comparison
    # against the ladder. Let the schema enforce the vocabulary instead of
    # hoping the prose matches.
    rung: Rung | None = Field(
        default=None, description="For a transfer gap, the rung where it stops holding."
    )
    shot: str | None = None
    cue_id: str | None = None
    confidence: Literal["high", "medium", "low"] = Field(
        description="Low when it rests on one or two entries, or when most entries have "
        "no rung recorded."
    )
    timing_caution: str | None = Field(
        default=None,
        description="Set only if acting on this now would be wrong for the time of year "
        "or the player's stage — a grip or swing rebuild during a competitive block, for "
        "instance. Say what to do instead and when.",
    )
    for_the_coach: str = Field(
        description="What you are handing the coach. A question to ask, a thing to watch "
        "for, or a decision to make. Never an instruction to the player, and never "
        "squash advice of your own."
    )


class PlayerReview(BaseModel):
    findings: list[Finding] = Field(
        description="Most important first. Three or four at most. If nothing is going "
        "wrong, return an empty list or a single 'progress' finding — inventing a "
        "problem for a player who does not have one is the worst failure here."
    )
    summary: str = Field(description="Two sentences on where this player is overall.")


INSTRUCTIONS = """
You are the Comparison agent. You are given a digest of counted facts about one
player, drawn from every coach's notes and the player's own shared reflections.
Find what no single coach can see.

What you are looking for, in priority order:

1. TRANSFER GAP. A shot with good evidence at solo, block or routine, and
   trouble at pattern, conditioned game or match. The ladder is a
   technical-to-tactical gradient: at the low rungs a player can still think
   about their own swing, at the high rungs they cannot. A cue that holds low
   and dies high has not been learned, only performed. Name the rung where it
   stops — that is the useful part, not the fact that something is wrong.

2. CHRONIC CUE. Chronic is a computed label, not a judgement for you to make.
   The digest marks a chronic cue with "<-- CHRONIC, and not moving". Nothing
   else is chronic, however often it recurs. A cue can appear seventeen times
   across twelve weeks and still not be chronic, because it is climbing the
   ladder — recurrence while the work moves to higher rungs is learning, not a
   blocker, and calling it a blocker tells a coach to fix something that is
   already fixing itself. Report chronic_cue only for a cue the digest has
   marked. Where one is marked, say how long it has been back and say plainly
   that it has stopped being a reminder. Do not suggest the fix.

3. COACH CONFLICT. Where two coaches wrote about the same shot in the same
   week, read both. The test is not whether the two are logically
   contradictory to an expert — "compact swing" and "fuller follow through"
   are perfectly compatible to a coach, and a child can still be stuck
   between them. The test is whether the player could reconcile them. If the
   player's own entry says they were unsure, or that they did neither and
   reverted to what they normally do, that is a coach conflict and it is the
   strongest evidence there is. Differently worded advice the player clearly
   acted on is not.

4. BLIND SPOT. The player's stated focus versus what the coaches keep writing
   about, or what the player's own reflections say versus what coaches saw.

Rules:

- Use the digest's numbers exactly. Never say "several times" when the digest
  says four, and never state a count the digest does not contain.
- Confidence is low when a finding rests on one or two entries.
- If the player is fine, say so. A clean player must come back clean. Inventing
  a problem is worse than missing one.
- Respect the time of year. If a finding implies a technical rebuild and the
  player is in a competitive block, set timing_caution and say when instead.
  A real problem can still be the wrong problem for this month.
- You never give coaching advice. You report the pattern and hand it over.
"""


async def review_player(player_id: str):
    agent = make_agent(INSTRUCTIONS, PlayerReview)
    week = db.week_of(clock.today_iso())
    today = f"Today is {clock.today():%A %d %B %Y}"
    if week:
        today += f", week {week['id']} of the block — {week['theme_name']}"
    prompt = f"{analysis.digest(player_id)}\n\n{today}.\nReview this player."
    return await run(agent, prompt, name="comparison")
