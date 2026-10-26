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
    # (week, rung level) per appearance, for working out which way it is going.
    points: list[tuple[int, int]] = field(default_factory=list)

    @property
    def span_weeks(self) -> int:
        return (max(self.weeks) - min(self.weeks)) if len(self.weeks) > 1 else 0

    @property
    def weeks_present(self) -> int:
        return len(set(self.weeks))

    @property
    def rung_trend(self) -> float | None:
        """How far up the ladder this cue has moved, first half to second.

        A cue being worked at block in August and holding in conditioned games
        by October has gone somewhere. One still being written about at the
        same rung after eleven weeks has not. Positive is climbing, zero is
        flat, negative is going backwards. None when there is too little to
        say.
        """
        runged = [(w, lvl) for w, lvl in self.points if lvl is not None]
        if len(runged) < 4:
            return None
        runged.sort()
        half = len(runged) // 2
        first = sum(lvl for _, lvl in runged[:half]) / half
        second = sum(lvl for _, lvl in runged[half:]) / (len(runged) - half)
        return round(second - first, 2)

    @property
    def direction(self) -> str:
        trend = self.rung_trend
        if trend is None:
            return "unclear"
        if trend >= 0.6:
            return "climbing"
        if trend <= -0.4:
            return "slipping"
        return "flat"

    @property
    def is_chronic(self) -> bool:
        """Still being written about, at the same level, after months of it.

        Recurrence alone is not the signal — a player's current focus turns up
        most weeks by definition, and in a dense record nearly every cue would
        qualify. What matters is recurrence that has not gone anywhere: the
        cue is still being raised late in the block, and the rung it is being
        raised at has not climbed.
        """
        return (self.count >= 8
                and self.span_weeks >= 8
                and self.weeks_present >= 6
                and self.direction != "climbing")


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
        run.points.append((week["id"] if week else 0,
                           RUNG_LEVEL.get(entry["rung"]) if entry["rung"] else None))
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
        chronic = "  <-- CHRONIC, and not moving" if run.is_chronic else ""
        trend = (f", ladder trend {run.rung_trend:+} ({run.direction})"
                 if run.rung_trend is not None else f", {run.direction}")
        lines.append(
            f"  {run.canonical} ({run.category}): {run.count}x across {weeks} "
            f"[{themes}], span {run.span_weeks} weeks, "
            f"{len(run.authors)} source(s){trend}{chronic}"
        )

    lines.append("\nLADDER EVIDENCE (low rungs first — technical rehearsal; "
                 "high rungs — tactical application):")
    # Every instance, deliberately. Capping this to the most recent three
    # per rung was tried: it cut the prompt by about 12% and broke
    # coach-conflict detection outright — with the full ladder the agent
    # finds Dev's two coaches contradicting each other in week 6, and with
    # the cap it finds nothing, consistently. The conflict is still printed
    # in its own section either way, so what the trimmed lines were
    # supplying was the surrounding context that makes two notes legible as
    # a disagreement rather than two separate observations. Reverted. See
    # the report's tokenomics section.
    PER_RUNG = 10**9
    for ladder in shot_ladders(player_id):
        lines.append(f"  {ladder.shot}:")
        for rung in db.RUNGS:
            at_rung = ladder.by_rung.get(rung, [])
            shown = sorted(at_rung, key=lambda e: e["occurred_on"])[-PER_RUNG:]
            for entry in shown:
                who = db.person(entry["author_id"])
                week = db.week_of(entry["occurred_on"])
                when = f"wk{week['id']}" if week else entry["occurred_on"]
                lines.append(
                    f"    [{rung}, {when}] ({who['role']}) {_clip(db.agent_text(entry))}")
            if len(at_rung) > PER_RUNG:
                lines.append(f"    [{rung}] … and {len(at_rung) - PER_RUNG} more "
                             f"at this rung, same picture")

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
        # Not capped, for the same reason as the ladder above.
        RECENT = 10**9
        newest = sorted(rest, key=lambda e: e["occurred_on"], reverse=True)
        for entry in newest[:RECENT]:
            who = db.person(entry["author_id"])
            week = db.week_of(entry["occurred_on"])
            where = f"wk{week['id']}" if week else entry["occurred_on"]
            lines.append(f"  [{where}, {entry['setting']}] ({who['role']} "
                         f"{who['name']}) {_clip(db.agent_text(entry), 200)}")
        if len(rest) > RECENT:
            lines.append(f"  … and {len(rest) - RECENT} older entries of this kind, "
                         f"counted above but not quoted")
    return "\n".join(lines)


# ---------------------------------------------------------------- periods

CATEGORIES = ("technical", "tactical", "physical", "psychological")


def period_stats(player_id: str, start: str, end: str, *, viewer: str = "player",
                 setting: str | None = None, author: str | None = None) -> dict:
    """Everything countable about one stretch of time.

    The recap agent gets these numbers rather than deriving them. "Eleven
    entries across six sessions, eight of them technical" has to be right —
    a recap that miscounts is worse than no recap, because a coach or a
    player will believe it.
    """
    rows = (db.entries_for_player(player_id) if viewer == "player"
            else db.entries_for_coach(player_id))
    rows = [e for e in rows if start <= e["occurred_on"] <= end]
    # Narrowing the record is not the same question as summarising all of it.
    # "What happens in my lessons" and "what happens in squad" have different
    # answers, and filtering before the agent reads is how you ask one.
    if setting:
        rows = [e for e in rows if e["setting"] == setting]
    if author:
        rows = [e for e in rows if e["author_id"] == author]

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

    runs = {r.cue_id: r for r in cue_runs(player_id)}
    recurring = sorted(
        ({"cue_id": c, "canonical": names.get(c, c), "count": n,
          "direction": runs[c].direction if c in runs else "unclear",
          "trend": runs[c].rung_trend if c in runs else None,
          "all_time": runs[c].count if c in runs else n,
          "chronic": bool(c in runs and runs[c].is_chronic)}
         for c, n in cue_hits.items() if n > 1),
        key=lambda r: -r["count"])

    counts = {c: len(v) for c, v in by_category.items()}
    emphasis = max(counts, key=lambda c: counts[c]) if rows else None

    return {
        "player_id": player_id,
        "start": start,
        "end": end,
        "setting": setting,
        "author": author,
        "rows": rows,
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
    narrowed = []
    if stats.get("setting"):
        narrowed.append(f"only {stats['setting']} entries")
    if stats.get("author"):
        who = db.person(stats["author"])
        narrowed.append(f"only what {who['name']} wrote" if who else "")
    lines = [
        f"PLAYER: {player['name']}, age {player['age']}",
        f"PERIOD: {stats['start']} to {stats['end']}"
        + (f"  [FILTERED: {', '.join(x for x in narrowed if x)}]" if narrowed else ""),
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
        lines.append("CAME BACK MORE THAN ONCE (in this period / all time / which way "
                     "it is going on the ladder):")
        for r in stats["recurring"]:
            trend = f"{r['trend']:+}" if r["trend"] is not None else "n/a"
            flag = "  <-- not moving" if r["chronic"] else ""
            lines.append(f"  {r['canonical']} [{r['cue_id']}]: {r['count']}x here, "
                         f"{r['all_time']}x all time, ladder {trend} "
                         f"({r['direction']}){flag}")

    for category, entries in stats["by_category"].items():
        if not entries:
            continue
        lines.append(f"\n{category.upper()} ({len(entries)}):")
        for entry in entries:
            who = db.person(entry["author_id"])
            lines.append(f"  [{entry['occurred_on']}, {entry['setting']}] "
                         f"({who['role']}) {_clip(db.agent_text(entry), 130)}")
    return "\n".join(lines)


def lessons(player_id: str, *, viewer: str = "player") -> list[dict]:
    """The private lessons, newest first, with both sides of each one.

    A lesson is where the technical focus gets set, so it is the spine of a
    player's term — but in a flat feed it sits among forty squad notes and
    reads like one of them. Pairing the coach's note with whatever the player
    wrote about the same lesson is the point: two accounts of one hour.
    """
    rows = (db.entries_for_player(player_id) if viewer == "player"
            else db.entries_for_coach(player_id))

    days: dict[str, dict] = {}
    for entry in rows:
        if entry["setting"] != "lesson":
            continue
        day = days.setdefault(entry["occurred_on"], {"on": entry["occurred_on"],
                                                     "coach": [], "player": []})
        day["coach" if entry["author_role"] == "coach" else "player"].append(entry)

    # A reflection written the same day belongs to that lesson in practice,
    # even though the player filed it as a reflection.
    for entry in rows:
        if entry["setting"] == "reflection" and entry["occurred_on"] in days:
            days[entry["occurred_on"]]["player"].append(entry)

    out = []
    for day in sorted(days.values(), key=lambda d: d["on"], reverse=True):
        week = db.week_of(day["on"])
        day["week"] = week
        day["coach_names"] = sorted({db.person(e["author_id"])["name"]
                                     for e in day["coach"]})
        out.append(day)
    return out


def coach_log(coach_id: str, start: str | None = None,
              end: str | None = None) -> list[dict]:
    """Everything this coach wrote, across every player, newest first.

    The coach-side views until now were all one player at a time, which is
    the wrong axis for a coach: between lessons they want their own week, not
    somebody's record.
    """
    with db.connect() as conn:
        sql = "SELECT * FROM entries WHERE author_id = ? AND author_role = 'coach'"
        args: list = [coach_id]
        if start:
            sql += " AND occurred_on >= ?"
            args.append(start)
        if end:
            sql += " AND occurred_on <= ?"
            args.append(end)
        rows = conn.execute(sql + " ORDER BY occurred_on DESC, id DESC", args).fetchall()

    out = []
    for entry in rows:
        player = db.person(entry["player_id"])
        out.append({"entry": entry, "player": player,
                    "week": db.week_of(entry["occurred_on"])})
    return out


def by_month(items: list[dict], key) -> list[tuple[str, list]]:
    """Group dated things into months, newest first.

    A term is a long list and a career is an unusable one, so anything that
    accumulates gets siloed by month before it reaches a screen.
    """
    from datetime import date as _d

    buckets: dict[str, list] = {}
    for item in items:
        day = key(item)
        buckets.setdefault(day[:7], []).append(item)
    return [(_d.fromisoformat(month + "-01").strftime("%B %Y"), rows)
            for month, rows in sorted(buckets.items(), reverse=True)]


def my_players(coach_id: str) -> list[dict]:
    """The players this coach actually gives lessons to.

    A coach's own page should show their own teaching, not the club's. Who
    they teach is not a roster someone maintains — it is whoever they have
    written lesson notes about.
    """
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT player_id, COUNT(*) AS lessons,
                      MAX(occurred_on) AS last_on, MIN(occurred_on) AS first_on
               FROM entries
               WHERE author_id = ? AND author_role = 'coach' AND setting = 'lesson'
               GROUP BY player_id""",
            (coach_id,),
        ).fetchall()
    out = []
    for row in rows:
        person = db.person(row["player_id"])
        if not person:
            continue
        focus = db.current_focus(row["player_id"])
        out.append({"id": person["id"], "name": person["name"], "age": person["age"],
                    "lessons": row["lessons"], "last_on": row["last_on"],
                    "first_on": row["first_on"],
                    "focus": focus["text"] if focus else None})
    return sorted(out, key=lambda p: p["last_on"], reverse=True)


def glance(player_id: str) -> dict:
    """What a coach needs in the four seconds before a squad starts.

    Not a record — a heads-up. What this player is on, what they have most
    recently been told, what keeps coming back from the coaches, and what
    keeps coming back from the player themselves. All counted, no model call,
    because this page gets opened between courts.
    """
    person = db.person(player_id)
    entries = db.entries_for_coach(player_id)
    coach_rows = [e for e in entries if e["author_role"] == "coach"]
    own_rows = [e for e in entries if e["author_role"] == "player"]

    with db.connect() as conn:
        focuses = conn.execute(
            """SELECT * FROM focuses WHERE player_id = ?
               ORDER BY resolved_on IS NULL DESC, set_on DESC LIMIT 4""",
            (player_id,)).fetchall()
        names = {r["id"]: r["canonical"]
                 for r in conn.execute("SELECT id, canonical FROM cues")}

    def top_cues(rows, limit=3):
        hits: dict[str, int] = defaultdict(int)
        for entry in rows:
            if entry["cue_id"]:
                hits[entry["cue_id"]] += 1
        ranked = sorted(hits.items(), key=lambda kv: -kv[1])[:limit]
        return [{"cue": names.get(c, c), "count": n} for c, n in ranked if n > 1]

    runs = {r.cue_id: r for r in cue_runs(player_id)}
    stuck = [r for r in runs.values() if r.is_chronic]

    return {
        "person": person,
        "focus": next((f for f in focuses if f["resolved_on"] is None), None),
        "minor": [f for f in focuses if f["resolved_on"] is not None][:2],
        "latest": coach_rows[-1] if coach_rows else None,
        "from_coaches": top_cues(coach_rows),
        "from_player": top_cues(own_rows),
        "stuck": stuck[:1],
        "last_seen": entries[-1]["occurred_on"] if entries else None,
    }
