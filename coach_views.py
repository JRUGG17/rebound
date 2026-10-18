"""Coach-, admin- and parent-facing screens.

Kept out of app.py, which was already carrying the player screens and every
callback. Nothing here calls a model except where a button says it will —
the squad card and the matrix are computed in SQL, so a coach can open them
between drills and they are instant and free.
"""

from __future__ import annotations

from dash import dcc, html

from core import analysis, clock, db
from core import playbook as pb

CATEGORY_ORDER = ("technical", "tactical", "physical", "psychological")

RUNG_LABELS = {
    "solo": "solo", "block": "block", "routine": "routine",
    "pattern": "pattern", "conditioned_game": "cond. game", "match": "match",
}


# ------------------------------------------------------------------ today

def squad_card():
    """The bleachers moment: what to lead the group feedback with."""
    overview = analysis.squad_overview()
    total = overview["total"]

    if overview["shared"]:
        top = overview["shared"][0]
        lead = html.Div([
            html.Div("Lead the group with", className="label"),
            html.Div(top["canonical"], className="lead-cue"),
            html.Div(f"{len(top['players'])} of {total} players have had this on court "
                     f"this week.", className="hint"),
        ], className="lead-box")
        others = [
            html.Div([
                html.Span(f"{len(s['players'])}/{total}", className="count-pill"),
                html.Span(s["canonical"], className="shared-cue"),
                html.Span(", ".join(s["players"]), className="hint"),
            ], className="shared-row")
            for s in overview["shared"][1:]
        ]
    else:
        lead = html.Div("No cue is shared across the squad this week — "
                        "feedback is individual.", className="empty")
        others = []

    return html.Div([
        html.H2("Squad card"),
        lead,
        *others,
        html.Div("Worth naming someone if they did it well, or if what they were "
                 "working on applies to the rest. Save the harder conversations for "
                 "one-to-one.", className="hint", style={"marginTop": "14px"}),
    ], className="card")


def week_control(coach_id: str, saved_msg: str | None = None):
    week = db.week_of(clock.today_iso())
    options = [{"label": f"{s.title()} Week", "value": s} for s in db.SHOTS] + [
        {"label": "Reset Week", "value": "reset"},
        {"label": "Attacking Week", "value": "attacking"},
        {"label": "Positional Driving Week", "value": "positional"},
    ]
    return html.Div([
        html.H2("Shot of the week"),
        html.Div([
            dcc.Dropdown(id="theme-pick", options=options,
                         value=week["theme_shot"] if week else None,
                         clearable=False, style={"width": "280px"}),
            html.Button("Set", id="set-theme", className="primary"),
            html.Span(saved_msg or "", className="hint"),
        ], className="composer-row"),
        html.Div(f"Week {week['id']} of the block · currently {week['theme_name']}"
                 if week else "No curriculum week for this date.",
                 className="hint", style={"marginTop": "8px"}),
    ], className="card")


def approvals_card(coach_id: str):
    pending = db.pending_approval(coach_id)
    if not pending:
        return html.Div([
            html.H2("Waiting on you"),
            html.Div("Nothing to release.", className="empty"),
        ], className="card")

    rows = []
    for entry in pending[:5]:
        player = db.person(entry["player_id"])
        rows.append(html.Div([
            html.Div(f"{player['name']} · {entry['occurred_on']}", className="meta"),
            html.Div(entry["raw_text"], className="body"),
            html.Div("No player version written yet — until there is one, this stays "
                     "a coach record and the player sees nothing.", className="hint"),
        ], className="entry"))

    return html.Div([
        html.H2(f"Waiting on you · {len(pending)}"),
        html.Div("Notes you have written that have not been released to the player.",
                 className="hint", style={"marginBottom": "10px"}),
        *rows,
    ], className="card")


def coach_today(coach_id: str, theme_msg: str | None = None):
    return html.Div([squad_card(), week_control(coach_id, theme_msg),
                     approvals_card(coach_id)])


# ------------------------------------------------------------------ players

def roster():
    overview = analysis.squad_overview()
    rows = []
    for player in overview["players"]:
        flags = []
        if player["chronic"]:
            run = player["chronic"][0]
            flags.append(html.Span(
                f"chronic · {run.canonical} ×{run.count} over {run.span_weeks}wk",
                className="tag chronic"))
        rows.append(html.Button([
            html.Div([
                html.Span(player["name"], className="roster-name"),
                html.Span(f"age {player['age']}", className="hint"),
            ]),
            html.Div(player["focus"] or "No focus set", className="roster-focus"),
            html.Div(flags or [html.Span("—", className="hint")]),
        ], id={"type": "open-player", "id": player["id"]}, className="roster-row"))

    return html.Div([
        html.H2("Players"),
        html.Div(rows, className="roster"),
    ], className="card")


def matrix_table(player_id: str):
    grid = analysis.matrix(player_id)
    if not grid:
        return html.Div("No entries carry both a shot and a rung yet.", className="empty")

    header = html.Tr([html.Th("")] + [html.Th(RUNG_LABELS[r]) for r in db.RUNGS])
    rows = []
    for shot, counts in grid.items():
        cells = [html.Td(shot, className="shot-name")]
        for rung in db.RUNGS:
            n = counts.get(rung, 0)
            cells.append(html.Td(str(n) if n else "", className=f"cell{' has' if n else ''}"))
        rows.append(html.Tr(cells))
    return html.Table([html.Thead(header), html.Tbody(rows)], className="matrix")


def finding_card(finding):
    kind_label = finding["kind"].replace("_", " ")
    bits = [
        html.Div([
            html.Span(kind_label, className=f"tag {finding['kind']}"),
            html.Span(finding["confidence"], className="tag"),
        ], className="meta"),
        html.Div(finding["headline"], className="finding-head"),
        html.Div(finding["evidence"], className="hint"),
    ]
    if finding.get("timing_caution"):
        bits.append(html.Div([html.Strong("Timing. "), finding["timing_caution"]],
                             className="timing-box"))
    bits.append(html.Div([html.Strong("For you. "), finding["for_the_coach"]],
                         className="for-coach"))
    return html.Div(bits, className="entry")


def player_detail(player_id: str, review: dict | None, running: bool,
                  focus_msg: str | None = None):
    player = db.person(player_id)
    focus = db.current_focus(player_id)

    if running:
        findings = [html.Div([html.Span(className="spinner"),
                              html.Span("  Reading every coach's notes…",
                                        className="hint")])]
    elif review:
        findings = ([finding_card(f) for f in review["findings"]]
                    or [html.Div("Nothing to flag. This player is on track.",
                                 className="empty")])
        findings.append(html.Div(review["summary"], className="hint",
                                 style={"marginTop": "12px"}))
    else:
        findings = [html.Div("Not run yet — this one costs a model call.",
                             className="empty")]

    return html.Div([
        html.Div([
            html.Button("‹ All players", id="back-roster", className="tab-btn"),
            html.Span("Their Calendar and Recap are in the sidebar under Journal.",
                      className="hint"),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px"}),
        html.Div(f"{player['name']} · age {player['age']}", className="hint",
                 style={"margin": "10px 0 4px"}),
        focus_control(player_id, focus_msg),

        html.Div([
            html.H2("Where the evidence sits"),
            html.Div("Low rungs rehearse, high rungs test.", className="hint",
                     style={"marginBottom": "12px"}),
            matrix_table(player_id),
        ], className="card"),

        html.Div([
            html.Div([
                html.H2("What no single coach can see"),
                html.Button("Run comparison", id="run-comparison", className="primary"),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center"}),
            html.Div(findings, style={"marginTop": "12px"}),
        ], className="card"),

        recent_notes(player_id),
    ])


RECENT_FOR_COACH = 6


def recent_notes(player_id: str):
    """The last handful, not the file.

    This used to print every entry on record — eighty-odd by half term, which
    is a page a coach scrolls past rather than reads. The history has three
    homes already: the calendar by day, Lessons by lesson, Recap by theme.
    """
    rows = list(reversed(db.entries_for_coach(player_id)))
    shown = rows[:RECENT_FOR_COACH]
    return html.Div([
        html.Div([
            html.H2("Latest"),
            html.Span(f"{len(rows)} on file · the rest is under Journal",
                      className="hint"),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "baseline"}),
        *[html.Div([
            html.Div([
                html.Span(e["occurred_on"], className="hint"),
                html.Span("coach" if e["author_role"] == "coach" else "player",
                          className=f"who-chip {'coach' if e['author_role'] == 'coach' else 'player'}"),
                html.Span(e["setting"], className="tag"),
                html.Span("private", className="tag")
                if e["visibility"] == "private" else html.Span(),
                html.Span("unsent", className="tag")
                if e["author_role"] == "coach" and not e["player_text_approved_at"]
                else html.Span(),
            ], className="meta"),
            html.Div(db.agent_text(e), className="body"),
        ], className=f"entry from-{'coach' if e['author_role'] == 'coach' else 'player'}")
          for e in shown],
    ], className="card")


# ------------------------------------------------------------------ resources

def resources(answer: dict | None, running: bool, section_no: int):
    sections = pb.sections()
    stats = pb.stats()
    current = pb.section(section_no) or sections[0]

    if running:
        result = [html.Span(className="spinner"),
                  html.Span("  Checking the playbook…", className="hint")]
    elif answer:
        cites = answer.get("citations") or []
        result = [
            html.Div(answer["answer"], className="body"),
            html.Div([
                html.Span("cites ", className="hint"),
                *[html.Span(c, className="tag") for c in cites],
                html.Span(" — not in the playbook", className="tag")
                if not answer["in_playbook"] else html.Span(),
            ], className="meta", style={"marginTop": "8px"}),
        ]
        if answer.get("note_for_admin"):
            result.append(html.Div([html.Strong("Flagged for the head of program "
                                                "development. "),
                                    answer["note_for_admin"]], className="timing-box"))
    else:
        result = [html.Div("Ask anything about how this academy teaches. Answers come "
                           "only from the playbook, with the section cited — if it is "
                           "not written down, you will be told so rather than guessed at.",
                           className="empty")]

    return html.Div([
        html.Div([
            html.H2("Ask the playbook"),
            dcc.Textarea(id="ask-box",
                         placeholder="What's the floor target for a B drive?"),
            html.Div([html.Button("Ask", id="ask-btn", className="primary"),
                      html.Span("Enter to ask · Shift+Enter for a new line",
                                className="hint")],
                     className="composer-row"),
            html.Div(result, style={"marginTop": "14px"}),
        ], className="card composer"),

        html.Div([
            html.H2(f"The playbook · {stats['sections']} sections, "
                    f"{stats['words']:,} words"),
            html.Div([
                html.Button(s.label, id={"type": "pb-section", "n": s.number},
                            className=f"tab-btn{' active' if s.number == current.number else ''}",
                            style={"textAlign": "left"})
                for s in sections
            ], className="pb-nav"),
        ], className="card"),

        html.Div(dcc.Markdown(current.body, className="pb-body"), className="card"),
    ])


# ------------------------------------------------------------------ parent

def parent_page(parent_id: str):
    parent = db.person(parent_id)
    child_id = parent["child_id"]
    child = db.person(child_id)
    focus = db.current_focus(child_id)
    entries = list(reversed(db.entries_for_parent(child_id)))

    cards = [html.Div([
        html.H2(f"{child['name']} · age {child['age']}"),
        html.Div(focus["text"] if focus else "No focus set", className="focus-text"),
        html.Div("This is what the coaches have set as the thing to work on.",
                 className="hint"),
    ], className="card focus-card")]

    shown = []
    for entry in entries:
        text = db.render_for(entry, "parent")
        if text is None:
            continue
        author = db.person(entry["author_id"])
        shown.append(html.Div([
            html.Div(f"{entry['occurred_on']} · {entry['setting']}", className="meta"),
            html.Div(text, className="body"),
            html.Div(f"— {author['name']}"
                     if author["role"] == "coach" else f"— {child['name'].split()[0]}",
                     className="byline"),
        ], className="entry"))

    cards.append(html.Div([
        html.H2("Training record"),
        html.Div("Read-only. You see what your child sees from their coaches, in the "
                 "same words. Children also have a private space for their own "
                 "reflections, which nobody reads — if anything written there suggests "
                 "they need support, you and a designated adult are told, and so are "
                 "they.", className="hint", style={"marginBottom": "14px"}),
        *(shown or [html.Div("Nothing yet.", className="empty")]),
    ], className="card"))
    return html.Div(cards)


# ------------------------------------------------------------------ add note

JOURNAL_PROMPT = (
    "What's on your mind? Reflect on the session here — how it went, what you were "
    "working on, how you felt about it. You don't have to share anything you don't "
    "want to."
)

SETTINGS = [("lesson", "Private lesson"), ("squad", "Squad"),
            ("tournament", "Tournament"), ("solo", "Solo assignment")]


def note_composer(draft: dict | None, running: bool):
    """Writing a lesson note. The thing the whole app is actually for.

    Two steps on one screen. The coach writes in their own language; the
    Organizer files it and proposes the version the player will read; the
    coach edits that and releases it. Nothing a model wrote reaches a child
    without passing through the second step.
    """
    draft = draft or {}
    organized = draft.get("organized")

    players = [{"label": f"{p['name']} (age {p['age']})", "value": p["id"]}
               for p in db.people("player")]

    form = html.Div([
        html.H2("New note"),
        html.Div([
            dcc.Dropdown(id="note-player", options=players,
                         value=draft.get("player_id"), placeholder="Which player",
                         clearable=False, style={"width": "260px"}),
            dcc.Dropdown(id="note-setting",
                         options=[{"label": label, "value": key}
                                  for key, label in SETTINGS],
                         value=draft.get("setting", "lesson"), clearable=False,
                         style={"width": "200px"}),
        ], className="composer-row", style={"marginBottom": "10px"}),
        dcc.Textarea(id="note-text", value=draft.get("text", "")),
        html.Div([
            html.Button("File it", id="file-note", className="primary"),
            html.Span([html.Span(className="spinner"),
                       html.Span("  Filing and drafting the player's version…",
                                 className="hint")] if running else "",
                      className="hint"),
        ], className="composer-row"),
    ], className="card composer")

    if not organized:
        return html.Div([form, html.Div([
            html.H2("How this works"),
            html.Div("You write once, in your own language. The note is filed against "
                     "the curriculum automatically, and a version for the player is "
                     "drafted for you to check. Nothing reaches them until you release "
                     "it.", className="tiein"),
        ], className="card")])

    # The coach chose the setting. The model may infer a different one from the
    # wording — "blocked drives" reads like squad even in a lesson note — and
    # when they disagree the coach is right, so show theirs.
    tags = [html.Span(organized["category"], className=f"tag {organized['category']}"),
            html.Span(dict(SETTINGS)[draft.get("setting", "lesson")].lower(),
                      className="tag")]
    for key in ("rung", "shot"):
        if organized.get(key):
            tags.append(html.Span(str(organized[key]).replace("_", " "), className="tag"))
    if organized.get("cue_id"):
        tags.append(html.Span(organized["cue_id"].replace("_", " "), className="tag"))

    warnings = []
    if organized.get("dropped_qualifier"):
        warnings.append(html.Div([
            html.Strong("Check this. "),
            "Something in your note — a caveat, a number, a condition — could not be "
            "carried into the player's version. Edit it before releasing.",
        ], className="timing-box"))
    if organized.get("mentions_injury"):
        warnings.append(html.Div([html.Strong("Injury mentioned. "),
                                  "This will be routed to the player's parent."],
                                 className="timing-box"))

    warning = organized.get("send_warning")

    tags = [html.Span(organized["category"], className=f"tag {organized['category']}"),
            html.Span(dict(SETTINGS)[draft.get("setting", "lesson")].lower(),
                      className="tag")]
    for key in ("rung", "shot"):
        if organized.get(key):
            tags.append(html.Span(str(organized[key]).replace("_", " "),
                                  className="tag"))
    if organized.get("cue_id"):
        tags.append(html.Span(organized["cue_id"].replace("_", " "), className="tag"))
    if organized.get("proposed_cue"):
        tags.append(html.Span(f"proposes: {organized['proposed_cue']}",
                              className="tag"))

    checks = []
    if warning:
        checks.append(html.Div([html.Strong("Before you send. "), warning],
                               className="timing-box"))
    if organized.get("mentions_injury"):
        checks.append(html.Div([html.Strong("Injury mentioned. "),
                                "This will be routed to the player's parent."],
                               className="timing-box"))
    if not checks:
        checks.append(html.Div("Nothing in it looks like it would land badly.",
                               className="hint"))

    player = db.person(draft["player_id"])
    return html.Div([
        form,
        html.Div([
            html.H2("Filed as"),
            html.Div(tags, className="meta", style={"marginBottom": "10px"}),
            html.Div(organized.get("summary", ""), className="body"),
        ], className="card"),
        html.Div([
            html.H2(f"What {player['name'].split()[0]} will read"),
            html.Div("Your words, exactly as you wrote them. Edit them here if you "
                     "want to say it differently — nothing is reworded for you.",
                     className="hint", style={"marginBottom": "10px"}),
            dcc.Textarea(id="note-player-text", value=draft.get("text", ""),
                         style={"minHeight": "110px"}),
            *checks,
            html.Div([
                html.Button("Send to player", id="release-note", className="primary"),
                html.Button("Keep as coach-only", id="keep-note", className="tab-btn"),
                html.Span(draft.get("saved", ""), className="hint"),
            ], className="composer-row"),
        ], className="card composer"),
    ])


# ------------------------------------------------------------------ journal

import calendar as _cal
from datetime import date as _date, timedelta


CATEGORY_ORDER = ("technical", "tactical", "physical", "psychological")


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _month_bounds(day: _date) -> tuple[str, str]:
    last = _cal.monthrange(day.year, day.month)[1]
    return (day.replace(day=1).isoformat(), day.replace(day=last).isoformat())


def calendar_view(player_id: str, viewer_role: str, offset: int = 0):
    """A month at a glance. Which days had anything, and what kind."""
    today = clock.today()
    month = today.month + offset
    year = today.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    first = _date(year, month, 1)
    start, end = _month_bounds(first)

    rows = (db.entries_for_player(player_id) if viewer_role == "player"
            else db.entries_for_coach(player_id))
    by_day: dict[str, list] = {}
    for entry in rows:
        if start <= entry["occurred_on"] <= end:
            by_day.setdefault(entry["occurred_on"], []).append(entry)

    weeks = _cal.Calendar(firstweekday=0).monthdatescalendar(year, month)
    grid = []
    for week in weeks:
        cells = []
        for day in week:
            if day.month != month:
                cells.append(html.Td("", className="cal-out"))
                continue
            entries = by_day.get(day.isoformat(), [])
            dots = [html.Span(className=f"dot {e['category'] or 'none'}")
                    for e in entries[:4]]
            cells.append(html.Td(
                html.Button([
                    html.Div(str(day.day), className="cal-day"),
                    html.Div(dots, className="cal-dots"),
                ], id={"type": "cal-day", "d": day.isoformat()}, className="cal-btn"),
                className="cal-cell" + (" has" if entries else "")
                + (" today" if day == today else "")))
        grid.append(html.Tr(cells))

    legend = html.Div([
        html.Span([html.Span(className=f"dot {c}"), " ", c], className="legend-item")
        for c in CATEGORY_ORDER
    ], className="legend")

    return html.Div([
        html.Div([
            html.Div([
                html.Button("‹", id="cal-prev", className="step dark"),
                html.Span(first.strftime("%B %Y"), className="cal-title"),
                html.Button("›", id="cal-next", className="step dark"),
            ], className="cal-head"),
            html.Table([
                html.Thead(html.Tr([html.Th(d) for d in
                                    ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")])),
                html.Tbody(grid),
            ], className="calendar"),
            legend,
            html.Div([
                html.Span(_plural(sum(len(v) for v in by_day.values()),
                                  "entry", "entries")
                          + " on " + _plural(len(by_day), "day", "days")
                          + " this month", className="hint"),
                html.Button(f"Recap {first.strftime('%B')}",
                            id={"type": "month-recap", "m": first.isoformat()},
                            className="tab-btn") if by_day else html.Span(),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "marginTop": "10px"}),
        ], className="card"),
    ])


DIRECTION_LABEL = {
    "climbing": "▲", "flat": "▬", "slipping": "▼", "new": "✦", "unclear": "·",
}

# Rolling windows rather than everything. A recap over the whole record costs
# the most and says the least — the useful question is almost always "what has
# been going on lately". Whole months are reachable from the calendar, where
# they are a deliberate choice rather than the default.
RANGES = [
    ("7", "Last 7 days"),
    ("14", "Last 2 weeks"),
    ("30", "Last 30 days"),
    ("block", "Whole block"),
]


def range_bounds(key: str) -> tuple[str, str, str]:
    today = clock.today()
    if key and key.startswith("month:"):
        first = _date.fromisoformat(key.split(":", 1)[1])
        a, b = _month_bounds(first)
        return a, min(b, today.isoformat()), first.strftime("%B %Y")
    if key == "block":
        return (clock.BLOCK_START.isoformat(), today.isoformat(), "the whole block")
    days = int(key) if str(key).isdigit() else 30
    start = today - timedelta(days=days - 1)
    label = {7: "the last 7 days", 14: "the last 2 weeks"}.get(days,
                                                              f"the last {days} days")
    return start.isoformat(), today.isoformat(), label


def recap_view(player_id: str, viewer_role: str, range_key: str,
               result: dict | None, running: bool):
    start, end, label = range_bounds(range_key)
    stats = analysis.period_stats(
        player_id, start, end, viewer="player" if viewer_role == "player" else "coach")
    all_rows = (db.entries_for_player(player_id) if viewer_role == "player"
                else db.entries_for_coach(player_id))
    all_rows = [e for e in all_rows if start <= e["occurred_on"] <= end]

    picker = html.Div([
        html.Button(label_, id={"type": "recap-range", "k": key},
                    className=f"tab-btn{' active' if key == range_key else ''}")
        for key, label_ in RANGES
    ], className="tab-row")

    tiles = html.Div([
        html.Div([html.Div("Entries", className="label"),
                  html.Div(str(stats["total"]), className="value")], className="stat"),
        html.Div([html.Div("Days trained", className="label"),
                  html.Div(str(stats["sessions"]), className="value")], className="stat"),
        *[html.Div([html.Div(c, className="label"),
                    html.Div(str(stats["counts"][c]), className="value")],
                   className="stat") for c in CATEGORY_ORDER],
    ], className="stat-row")

    if running:
        body = [html.Span(className="spinner"),
                html.Span("  Reading it back…", className="hint")]
    elif not stats["total"]:
        body = [html.Div(f"Nothing recorded for {label}.", className="empty")]
    elif result:
        body = [
            html.Div(result["headline"], className="recap-headline"),
            html.Div(result["overview"], className="recap-overview"),
        ]
        for theme in result["themes"]:
            # The entries behind a theme: by its cue where it has one, by
            # category otherwise. This is the "click in for the detail" half —
            # the theme is the point, the days are the receipts.
            if theme.get("cue_id"):
                backing = [e for e in all_rows if e["cue_id"] == theme["cue_id"]]
            else:
                backing = stats["by_category"].get(theme["category"], [])
            body.append(html.Details([
                html.Summary([
                    html.Span(DIRECTION_LABEL.get(theme["direction"], "·"),
                              className=f"arrow {theme['direction']}"),
                    html.Div([
                        html.Div(theme["title"], className="theme-title"),
                        html.Div([
                            html.Span(theme["category"],
                                      className=f"tag {theme['category']}"),
                            html.Span(theme["evidence"], className="hint"),
                        ], className="meta"),
                    ], style={"flex": "1"}),
                ]),
                html.Div([
                    html.Div(theme["what_it_is"], className="theme-body"),
                    html.Div(f"{_plural(len(backing), 'entry', 'entries')} behind this",
                             className="label", style={"marginTop": "14px"}),
                    *[html.Div([
                        html.Div(" · ".join(filter(None, [
                            e["occurred_on"], e["setting"],
                            e["rung"].replace("_", " ") if e["rung"] else None])),
                            className="meta"),
                        html.Div(db.render_for(e, viewer_role) or db.agent_text(e),
                                 className="body"),
                    ], className="entry") for e in backing[-12:]],
                ], className="bucket-body"),
            ], className="bucket"))
        if result.get("gap"):
            body.append(html.Div([html.Strong("Gap. "), result["gap"]],
                                 className="timing-box"))
    else:
        body = [html.Div("Pick a stretch of time and read it back. "
                         "Costs one model call.", className="empty")]

    return html.Div([
        html.Div([
            html.Div([
                html.H2(f"Recap · {label}"),
                html.Button("Read it back", id="run-recap", className="primary"),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center"}),
            picker,
            tiles,
            html.Div(body, style={"marginTop": "6px"}),
        ], className="card"),
    ])


def day_view(player_id: str, viewer_role: str, day: str,
             summary: dict | None, running: bool, saving: bool):
    """One day: everything written, plus somewhere to add to it.

    Backfilling matters more than it looks. A player who remembers on Thursday
    what happened on Tuesday should be able to put it on Tuesday, or the
    record drifts and the calendar stops meaning anything.
    """
    rows = (db.entries_for_player(player_id) if viewer_role == "player"
            else db.entries_for_coach(player_id))
    entries = [e for e in rows if e["occurred_on"] == day]
    week = db.week_of(day)
    is_past = day < clock.today_iso()
    pretty = _date.fromisoformat(day).strftime("%A %-d %B %Y")

    if running:
        head = [html.Span(className="spinner"),
                html.Span("  Reading the day back…", className="hint")]
    elif summary:
        head = [html.Div(summary["what_happened"], className="recap-overview")]
        if summary.get("fits_in"):
            head.append(html.Div([html.Strong("In context. "), summary["fits_in"]],
                                 className="recur-box"))
    elif entries:
        head = [html.Div("Nothing read back yet.", className="empty")]
    else:
        head = []

    cards = []
    for entry in entries:
        text = db.render_for(entry, viewer_role)
        if text is None:
            continue
        author = db.person(entry["author_id"])
        meta = [html.Span(" · ".join(filter(None, [
            entry["setting"],
            entry["rung"].replace("_", " ") if entry["rung"] else None,
            entry["shot"]])))]
        if entry["category"]:
            meta.append(html.Span(entry["category"], className=f"tag {entry['category']}"))
        if entry["visibility"] == "private":
            meta.append(html.Span("private", className="tag"))
        cards.append(html.Div([
            html.Div(meta, className="meta"),
            html.Div(text, className="body"),
            html.Div(f"— {author['name']}" if author["role"] == "coach"
                     else "— you", className="byline"),
        ], className="entry"))

    composer = []
    if viewer_role == "player":
        composer = [html.Div([
            html.H2("Add to this day" if entries else "Nothing here yet"),
            html.Div(
                "You can still add to a day that has passed — put it on the day it "
                "happened and the record stays straight."
                if is_past else
                "How did it go? A sentence is plenty.", className="hint",
                style={"marginBottom": "10px"}),
            dcc.Textarea(id="day-text"),
            html.Div([
                html.Button("🎤", id="day-mic", className="mic", title="Speak instead"),
                html.Button("Add to this day", id="day-save", className="primary"),
                html.Button("🔒 Keep private", id="day-save-private", className="tab-btn"),
                html.Span([html.Span(className="spinner"),
                           html.Span("  Filing it…", className="hint")] if saving else ""),
            ], className="composer-row"),
        ], className="card composer")]

    return html.Div([
        html.Div([
            html.Button("‹ Back to the month", id="day-back", className="tab-btn"),
            html.H2(pretty),
            html.Div(html.Span(week["theme_name"], className="theme-pill")
                     if week else "", style={"marginBottom": "8px"}),
            html.Div([
                html.Button("Read this day back", id="run-day", className="primary"),
            ] if entries else [], className="composer-row"),
            *head,
        ], className="card"),
        html.Div([html.H2(_plural(len(cards), "entry", "entries")), *cards],
                 className="card") if cards else html.Span(),
        *composer,
    ])


PRIVATE_PROMPT = (
    "Whatever you want. Nobody reads this but you — how you're feeling, what's "
    "annoying you, things you'd rather not say out loud yet. There's no wrong "
    "thing to put here."
)


def lessons_view(player_id: str, viewer_role: str, open_on: str | None,
                 saving: bool, arc: dict | None = None, running: bool = False):
    """Lesson by lesson: what the coach wrote, what the player wrote back."""
    items = analysis.lessons(player_id, viewer="player" if viewer_role == "player"
                             else "coach")
    if not items:
        return html.Div([html.H2("Lessons"),
                         html.Div("No lessons on record yet.", className="empty")],
                        className="card")

    cards = []
    months = analysis.by_month([{"on": i["on"], "lesson": i} for i in items],
                               lambda i: i["on"])
    newest_month = months[0][0] if months else None
    for lesson in items:
        day = lesson["on"]
        pretty = _date.fromisoformat(day).strftime("%a %-d %b")
        is_open = (open_on or items[0]["on"]) == day

        coach_block = [html.Div([
            html.Div([html.Span("coach", className="who-chip coach"),
                      html.Span(db.person(e["author_id"])["name"], className="hint")],
                     className="meta"),
            html.Div(db.render_for(e, viewer_role) or "", className="body"),
        ], className="entry from-coach") for e in lesson["coach"]
            if db.render_for(e, viewer_role)]

        player_block = [html.Div([
            html.Div(html.Span("you" if viewer_role == "player" else "player",
                               className="who-chip player"), className="meta"),
            html.Div(db.render_for(e, viewer_role) or "", className="body"),
        ], className="entry from-player") for e in lesson["player"]
            if db.render_for(e, viewer_role)]

        if not player_block:
            player_block = [html.Div(
                "You didn't write anything about this lesson."
                if viewer_role == "player" else "Nothing from the player.",
                className="empty")]

        body = [
            html.Div("What your coach wrote" if viewer_role == "player"
                     else "Coach", className="label"),
            *(coach_block or [html.Div("Nothing recorded.", className="empty")]),
            html.Div("What you wrote" if viewer_role == "player" else "Player",
                     className="label", style={"marginTop": "16px"}),
            *player_block,
        ]

        if viewer_role == "player":
            body += [
                html.Hr(style={"border": 0, "borderTop": "1px solid var(--line)",
                               "margin": "16px 0"}),
                dcc.Textarea(id={"type": "lesson-text", "d": day},
                             ),
                html.Div([
                    html.Button("🎤", id={"type": "lesson-mic", "d": day},
                            className="mic", title="Speak instead"),
                html.Button("Add to this lesson",
                                id={"type": "lesson-save", "d": day},
                                className="primary"),
                    html.Span([html.Span(className="spinner"),
                               html.Span("  Filing it…", className="hint")]
                              if saving and is_open else ""),
                ], className="composer-row"),
            ]

        cards.append(html.Details([
            html.Summary([
                html.Div([
                    html.Span(pretty, className="lesson-date"),
                    html.Span(lesson["week"]["theme_name"] if lesson["week"] else "",
                              className="tag"),
                ]),
                html.Span(f"{len(lesson['coach'])} coach · "
                          f"{len(lesson['player'])} yours"
                          if viewer_role == "player" else
                          f"{len(lesson['coach'])} coach · {len(lesson['player'])} player",
                          className="hint"),
            ]),
            html.Div(body, className="bucket-body composer"),
        ], className="bucket", open=is_open))

    if running:
        thread = [html.Span(className="spinner"),
                  html.Span("  Reading the whole thread…", className="hint")]
    elif arc:
        thread = [html.Div(arc["overview"], className="recap-overview")]
        for phase in arc["phases"]:
            thread.append(html.Div([
                html.Div(phase["span"], className="label"),
                html.Div(phase["focus"], className="theme-title"),
                html.Div(phase["what_happened"], className="theme-body"),
            ], className="entry"))
        if arc.get("carried_over"):
            thread.append(html.Div([
                html.Div("Still carrying over", className="label"),
                *[html.Div(line, className="recur-line") for line in arc["carried_over"]],
            ], className="recur-box"))
        if arc.get("never_answered"):
            thread.append(html.Div([
                html.Strong("Raised and never picked up. "),
                html.Div([html.Div(line) for line in arc["never_answered"]]),
            ], className="timing-box"))
    else:
        thread = [html.Div("Read the lessons end to end and see how the focus has "
                           "moved. Costs one model call.", className="empty")]

    return html.Div([
        html.Div([
            html.Div([
                html.H2("The thread"),
                html.Button("Read the lessons back", id="run-lesson-arc",
                            className="primary"),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center"}),
            html.Div(thread, style={"marginTop": "10px"}),
        ], className="card"),
        html.Div([
            html.H2(f"Lessons · {len(items)}"),
            html.Div("Your private lessons, newest first. The coach's note and yours, "
                     "side by side." if viewer_role == "player"
                     else "Private lessons, newest first.", className="hint",
                     style={"marginBottom": "12px"}),
            # Grouped by month: a term is a long list and a couple of years is
            # an unusable one.
            *[html.Div([
                html.Div(month, className="side-heading",
                         style={"paddingLeft": 0}),
                *[c for c, lesson in zip(cards, items)
                  if _date.fromisoformat(lesson["on"]).strftime("%B %Y") == month],
            ]) for month, _rows in months],
        ], className="card"),
    ])


# ------------------------------------------------------------------ coach's own

def coach_log_view(coach_id: str, offset: int = 0):
    """A coach's own teaching log, their lessons and notes, grouped by month."""
    items = analysis.coach_log(coach_id)
    if not items:
        return html.Div([html.H2("My log"),
                         html.Div("You have not written anything yet.",
                                  className="empty")], className="card")

    lessons = [i for i in items if i["entry"]["setting"] == "lesson"]
    players = {i["player"]["id"] for i in items}
    pending = len(db.pending_approval(coach_id))

    cards = [html.Div([
        html.Div([
            html.Div([html.Div("Notes written", className="label"),
                      html.Div(str(len(items)), className="value")], className="stat"),
            html.Div([html.Div("Lessons", className="label"),
                      html.Div(str(len(lessons)), className="value")], className="stat"),
            html.Div([html.Div("Players", className="label"),
                      html.Div(str(len(players)), className="value")], className="stat"),
            html.Div([html.Div("Unreleased", className="label"),
                      html.Div(str(pending), className="value"),
                      html.Div("not shown to the player", className="sub")],
                     className="stat"),
        ], className="stat-row"),
    ])]

    for month, rows in analysis.by_month(items, lambda i: i["entry"]["occurred_on"]):
        month_lessons = [r for r in rows if r["entry"]["setting"] == "lesson"]
        cards.append(html.Details([
            html.Summary([
                html.Span(month, className="lesson-date"),
                html.Span(f"{_plural(len(rows), 'note', 'notes')} · "
                          f"{_plural(len(month_lessons), 'lesson', 'lessons')}",
                          className="hint"),
            ]),
            html.Div([html.Div([
                html.Div([
                    html.Span(r["entry"]["occurred_on"], className="hint"),
                    html.Span(r["player"]["name"], className="who-chip player"),
                    html.Span(r["entry"]["setting"], className="tag"),
                    html.Span("unreleased", className="tag")
                    if not r["entry"]["player_text_approved_at"] else html.Span(),
                ], className="meta"),
                html.Div(r["entry"]["raw_text"], className="body"),
            ], className="entry from-coach") for r in rows], className="bucket-body"),
        ], className="bucket", open=(month == analysis.by_month(
            items, lambda i: i["entry"]["occurred_on"])[0][0])))

    return html.Div([
        html.H2("My log"),
        html.Div("Everything you have written, across all your players, newest "
                 "first.", className="hint", style={"marginBottom": "12px"}),
        *cards,
    ], className="card")


def focus_control(player_id: str, saved: str | None = None):
    """Setting a player's focus — the thing a lesson is actually for."""
    current = db.current_focus(player_id)
    history = []
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT * FROM focuses WHERE player_id = ?
               ORDER BY set_on DESC LIMIT 6""", (player_id,)).fetchall()
    for row in rows:
        coach = db.person(row["coach_id"])
        history.append(html.Div([
            html.Div([html.Span(row["set_on"], className="hint"),
                      html.Span(coach["name"] if coach else "", className="hint"),
                      html.Span("current" if row["resolved_on"] is None
                                else "ended", className="tag")], className="meta"),
            html.Div(row["text"], className="body"),
        ], className="entry"))

    return html.Div([
        html.H2("Focus"),
        html.Div(current["text"] if current else "No focus set",
                 className="focus-text"),
        html.Div("What this player is working on between lessons. Setting a new one "
                 "closes the old.", className="hint", style={"margin": "8px 0 12px"}),
        dcc.Textarea(id="focus-text", style={"minHeight": "60px"}),
        html.Div([
            dcc.Dropdown(id="focus-category",
                         options=[{"label": c.title(), "value": c}
                                  for c in CATEGORY_ORDER],
                         value="technical", clearable=False,
                         style={"width": "190px"}),
            html.Button("Set as the focus", id="set-focus", className="primary"),
            html.Span(saved or "", className="hint"),
        ], className="composer-row"),
        html.Details([
            html.Summary(html.Span("Earlier focuses", className="hint")),
            html.Div(history, className="bucket-body"),
        ], className="bucket", style={"marginTop": "14px"}) if history else html.Span(),
    ], className="card focus-card composer")
