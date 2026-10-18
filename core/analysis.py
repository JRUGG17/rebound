"""Counting, done in Python. Judgement is left to the model.

The Comparison agent could be handed fifty raw entries and asked to notice
things, but counting is the one job a language model is worst at and SQL is
best at. So everything countable happens here — how many times a cue came
back, which weeks, which rungs of the ladder a shot has evidence on, which
two coaches wrote about the same thing in the same week — and the agent
receives a short digest of exact facts to interpret.

Three things follow from that. The numbers in a finding are real rather than
approximated. The prompt is a few hundred tokens instead of several thousand.
And a run is reproducible, because the arithmetic does not change between
calls.

Nothing here reads a player's private entries: it all goes through
db.entries_for_coach.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from core import db

# How far up the ladder an entry sits. Used to tell "clean in drills" from
# "falls apart in a game" without the model having to know the ordering.
RUNG_LEVEL = {rung: i for i, rung in enumerate(db.RUNGS)}
LOW_RUNGS = ("solo", "block", "routine")
HIGH_RUNGS = ("pattern", "conditioned_game", "match")


@dataclass
class CueRun:
    """One cue, and every time it has come back."""

    cue_id: str
    canonical: str
    category: str
    count: int = 0
    weeks: list[int] = field(default_factory=list)
    theme_weeks: list[str] = field(default_factory=list)
    authors: set[str] = field(default_factory=set)
    first_on: str = ""
    last_on: str = ""

    @property
    def span_weeks(self) -> int:
        return (max(self.weeks) - min(self.weeks)) if len(self.weeks) > 1 else 0

    @property
    def is_chronic(self) -> bool:
        """Back three or more times, over at least two months.

        The curriculum rotates every four weeks, so three appearances of the
        same cue is not three reminders — it is the same unresolved problem
        surviving two full passes through the shot.
        """
        return self.count >= 3 and self.span_weeks >= 8


@dataclass
class ShotLadder:
    """Where a shot has evidence, low to high."""

    shot: str
    by_rung: dict[str, list] = field(default_factory=lambda: defaultdict(list))

    @property
    def highest_with_evidence(self) -> str | None:
        present = [r for r in db.RUNGS if self.by_rung.get(r)]
        return present[-1] if present else None

    @property
    def has_both_ends(self) -> bool:
        low = any(self.by_rung.get(r) for r in LOW_RUNGS)
        high = any(self.by_rung.get(r) for r in HIGH_RUNGS)
        return low and high


def cue_runs(player_id: str) -> list[CueRun]:
    """Every canonical cue this player has, most-recurring first."""
    with db.connect() as conn:
        cues = {r["id"]: r for r in conn.execute("SELECT * FROM cues")}

    runs: dict[str, CueRun] = {}
    for entry in db.entries_for_coach(player_id):
        cue_id = entry["cue_id"]
        if not cue_id or cue_id not in cues:
            continue
        run = runs.setdefault(cue_id, CueRun(
            cue_id=cue_id,
            canonical=cues[cue_id]["canonical"],
            category=cues[cue_id]["category"],
        ))
        week = db.week_of(entry["occurred_on"])
        run.count += 1
        if week:
            run.weeks.append(week["id"])
            if week["theme_name"] not in run.theme_weeks:
                run.theme_weeks.append(week["theme_name"])
        run.authors.add(entry["author_id"])
        run.first_on = run.first_on or entry["occurred_on"]
        run.last_on = entry["occurred_on"]
    return sorted(runs.values(), key=lambda r: (-r.count, r.cue_id))


def shot_ladders(player_id: str) -> list[ShotLadder]:
    """Each shot's entries, bucketed by rung."""
    ladders: dict[str, ShotLadder] = {}
    for entry in db.entries_for_coach(player_id):
        if not entry["shot"] or not entry["rung"]:
            continue
        ladder = ladders.setdefault(entry["shot"], ShotLadder(shot=entry["shot"]))
        ladder.by_rung[entry["rung"]].append(entry)
    return sorted(ladders.values(), key=lambda s: s.shot)


def coach_overlaps(player_id: str) -> list[dict]:
    """Weeks where two different coaches wrote about the same shot.

    Not a contradiction on its own — just the only place one can occur. The
    agent reads the pair and decides whether they actually disagree.
    """
    buckets: dict[tuple, list] = defaultdict(list)
    for entry in db.entries_for_coach(player_id):
        if entry["author_role"] != "coach":
            continue
        week = db.week_of(entry["occurred_on"])
        if not week:
            continue
        buckets[(week["id"], entry["shot"])].append(entry)

    overlaps = []
    for (week_id, shot), entries in sorted(buckets.items()):
        authors = {e["author_id"] for e in entries}
        if len(authors) > 1:
            overlaps.append({"week": week_id, "shot": shot, "entries": entries})
    return overlaps


def matrix(player_id: str) -> dict:
    """shot × rung grid, for the UI. Counts only, no judgement."""
    grid: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(db.RUNGS, 0))
    for entry in db.entries_for_coach(player_id):
        if entry["shot"] and entry["rung"]:
            grid[entry["shot"]][entry["rung"]] += 1
    return {shot: dict(rungs) for shot, rungs in sorted(grid.items())}


def squad_overview() -> dict:
    """What the whole squad is working on, and where it overlaps.

    This is the bleachers moment. Feedback after a drill is given to the group,
    nobody is singled out, the group is mixed-level, and the coach has about
    two minutes and no notes. Knowing that four of eight players are on the
    same cue turns that two minutes from a guess into a decision.

    Counted in Python. No model call, so a coach can open this between drills
    and it is instant and free.
    """
    from core import clock

    week = db.week_of(clock.today_iso())
    week_start = week["starts_on"] if week else None

    players = []
    by_cue: dict[str, list[str]] = defaultdict(list)

    for person in db.people("player"):
        focus = db.current_focus(person["id"])
        chronic = [r for r in cue_runs(person["id"]) if r.is_chronic]
        entries = db.entries_for_coach(person["id"])
        # Overlap is drawn from what has come up on court this week, not from
        # the standing lesson focus. A coach on the bleachers cares what the
        # group has been doing in the last few sessions.
        this_week = [e for e in entries if week_start and e["occurred_on"] >= week_start]
        week_cues = {e["cue_id"] for e in this_week if e["cue_id"]}

        players.append({
            "id": person["id"],
            "name": person["name"],
            "age": person["age"],
            "focus": focus["text"] if focus else None,
            "cue_id": focus["cue_id"] if focus else None,
            "chronic": chronic,
            "week_cues": week_cues,
            "entries_this_week": len(this_week),
            "last_entry": entries[-1]["occurred_on"] if entries else None,
        })
        for cue_id in week_cues:
            by_cue[cue_id].append(person["name"].split()[0])

    with db.connect() as conn:
        cues = {r["id"]: r["canonical"] for r in conn.execute("SELECT id, canonical FROM cues")}

    shared = [
        {"cue_id": cue_id, "canonical": cues.get(cue_id, cue_id), "players": names}
        for cue_id, names in sorted(by_cue.items(), key=lambda kv: -len(kv[1]))
        if len(names) > 1
    ]
    return {"players": players, "shared": shared, "total": len(players)}


def _clip(text: str, limit: int = 150) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def digest(player_id: str) -> str:
    """The compact, exact brief the Comparison agent reads instead of raw rows."""
    player = db.person(player_id)
    focus = db.current_focus(player_id)
    lines = [f"PLAYER: {player['name']}, age {player['age']}"]
    if focus:
        lines.append(f"CURRENT FOCUS (set {focus['set_on']}): {focus['text']}")

    lines.append("\nRECURRING CUES (counted, not estimated):")
    runs = cue_runs(player_id)
    if not runs:
        lines.append("  none tagged yet")
    for run in runs:
        weeks = ", ".join(f"wk{w}" for w in sorted(set(run.weeks)))
        themes = "; ".join(run.theme_weeks)
        chronic = "  <-- CHRONIC" if run.is_chronic else ""
        lines.append(
            f"  {run.canonical} ({run.category}): {run.count}x across {weeks} "
            f"[{themes}], span {run.span_weeks} weeks, "
            f"{len(run.authors)} source(s){chronic}"
        )

    lines.append("\nLADDER EVIDENCE (low rungs first — technical rehearsal; "
                 "high rungs — tactical application):")
    for ladder in shot_ladders(player_id):
        lines.append(f"  {ladder.shot}:")
        for rung in db.RUNGS:
            for entry in ladder.by_rung.get(rung, []):
                who = db.person(entry["author_id"])
                week = db.week_of(entry["occurred_on"])
                when = f"wk{week['id']}" if week else entry["occurred_on"]
                lines.append(
                    f"    [{rung}, {when}] ({who['role']}) {_clip(db.agent_text(entry))}")

    overlaps = coach_overlaps(player_id)
    if overlaps:
        lines.append("\nSAME WEEK, SAME SHOT, DIFFERENT COACHES "
                     "(check whether they actually conflict):")
        for overlap in overlaps:
            lines.append(f"  week {overlap['week']}, {overlap['shot']}:")
            for entry in overlap["entries"]:
                who = db.person(entry["author_id"])
                lines.append(f"    {who['name']}: {_clip(db.agent_text(entry))}")

    # Entries with no rung are not ladder evidence, but they are often the most
    # revealing thing in the record — a player saying they did not know which
    # coach to listen to has no rung and no shot technique in it at all. Listing
    # them only as a count, as this did at first, hid exactly the entries the
    # agent most needed. Show them.
    ladder_ids = {e["id"] for ladder in shot_ladders(player_id)
                  for entries in ladder.by_rung.values() for e in entries}
    rest = [e for e in db.entries_for_coach(player_id) if e["id"] not in ladder_ids]
    if rest:
        lines.append("\nEVERYTHING ELSE (no rung recorded — lesson notes, reflections, "
                     "results). Not ladder evidence, but read it:")
        for entry in rest:
            who = db.person(entry["author_id"])
            week = db.week_of(entry["occurred_on"])
            where = f"wk{week['id']}" if week else entry["occurred_on"]
            lines.append(f"  [{where}, {entry['setting']}] ({who['role']} "
                         f"{who['name']}) {_clip(db.agent_text(entry), 200)}")
    return "\n".join(lines)


# ---------------------------------------------------------------- periods

CATEGORIES = ("technical", "tactical", "physical", "psychological")


def period_stats(player_id: str, start: str, end: str, *, viewer: str = "player") -> dict:
    """Everything countable about one stretch of time.

    The recap agent gets these numbers rather than deriving them. "Eleven
    entries across six sessions, eight of them technical" has to be right —
    a recap that miscounts is worse than no recap, because a coach or a
    player will believe it.
    """
    rows = (db.entries_for_player(player_id) if viewer == "player"
            else db.entries_for_coach(player_id))
    rows = [e for e in rows if start <= e["occurred_on"] <= end]

    by_category: dict[str, list] = {c: [] for c in CATEGORIES}
    by_setting: dict[str, int] = defaultdict(int)
    by_shot: dict[str, int] = defaultdict(int)
    by_rung: dict[str, int] = defaultdict(int)
    cue_hits: dict[str, int] = defaultdict(int)
    days: set[str] = set()

    for entry in rows:
        if entry["category"] in by_category:
            by_category[entry["category"]].append(entry)
        by_setting[entry["setting"]] += 1
        days.add(entry["occurred_on"])
        if entry["shot"]:
            by_shot[entry["shot"]] += 1
        if entry["rung"]:
            by_rung[entry["rung"]] += 1
        if entry["cue_id"]:
            cue_hits[entry["cue_id"]] += 1

    with db.connect() as conn:
        names = {r["id"]: r["canonical"]
                 for r in conn.execute("SELECT id, canonical FROM cues")}

    recurring = sorted(
        ({"cue_id": c, "canonical": names.get(c, c), "count": n}
         for c, n in cue_hits.items() if n > 1),
        key=lambda r: -r["count"])

    counts = {c: len(v) for c, v in by_category.items()}
    emphasis = max(counts, key=lambda c: counts[c]) if rows else None

    return {
        "player_id": player_id,
        "start": start,
        "end": end,
        "total": len(rows),
        "sessions": len(days),
        "by_category": by_category,
        "counts": counts,
        "untouched": [c for c in CATEGORIES if not counts[c]],
        "emphasis": emphasis if rows and counts[emphasis] else None,
        "by_setting": dict(by_setting),
        "by_shot": dict(by_shot),
        "by_rung": dict(by_rung),
        "recurring": recurring,
    }


def period_digest(stats: dict) -> str:
    """The compact brief the recap agent reads."""
    player = db.person(stats["player_id"])
    lines = [
        f"PLAYER: {player['name']}, age {player['age']}",
        f"PERIOD: {stats['start']} to {stats['end']}",
        f"COUNTED: {stats['total']} entries across {stats['sessions']} days "
        f"({', '.join(f'{k} {v}' for k, v in stats['by_setting'].items()) or 'none'})",
        f"BY CATEGORY: " + ", ".join(f"{c} {n}" for c, n in stats["counts"].items()),
    ]
    if stats["untouched"]:
        lines.append(f"NOTHING RECORDED FOR: {', '.join(stats['untouched'])}")
    if stats["by_shot"]:
        lines.append("SHOTS: " + ", ".join(f"{k} {v}" for k, v in stats["by_shot"].items()))
    if stats["by_rung"]:
        lines.append("RUNGS: " + ", ".join(f"{k} {v}" for k, v in stats["by_rung"].items()))
    if stats["recurring"]:
        lines.append("CAME BACK MORE THAN ONCE: " + "; ".join(
            f"{r['canonical']} x{r['count']}" for r in stats["recurring"]))

    for category, entries in stats["by_category"].items():
        if not entries:
            continue
        lines.append(f"\n{category.upper()} ({len(entries)}):")
        for entry in entries:
            who = db.person(entry["author_id"])
            lines.append(f"  [{entry['occurred_on']}, {entry['setting']}] "
                         f"({who['role']}) {_clip(db.agent_text(entry), 130)}")
    return "\n".join(lines)
