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
        html.Div("Names are here for your own reference. Group feedback does not "
                 "single anyone out.", className="hint",
                 style={"marginTop": "14px"}),
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


def player_detail(player_id: str, review: dict | None, running: bool):
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
        html.Button("‹ All players", id="back-roster", className="tab-btn"),
        html.Div([
            html.H2("Focus"),
            html.Div(focus["text"] if focus else "No focus set", className="focus-text"),
            html.Div(f"{player['name']} · age {player['age']}", className="hint"),
        ], className="card focus-card"),

        html.Div([
            html.H2("Where the evidence sits"),
            html.Div("Low rungs are technical rehearsal; high rungs are tactical "
                     "application. A shot with entries low and nothing high has not "
                     "been tested under pressure.", className="hint",
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

        html.Div([
            html.H2("Everything on file"),
            *[html.Div([
                html.Div(" · ".join(filter(None, [
                    e["occurred_on"], e["setting"], e["rung"], e["shot"],
                    "PRIVATE" if e["visibility"] == "private" else None,
                    "FLAGGED" if e["flagged_injection"] else None,
                ])), className="meta"),
                html.Div(db.agent_text(e), className="body"),
                html.Div(f"— {db.person(e['author_id'])['name']}", className="byline"),
            ], className="entry") for e in reversed(db.entries_for_coach(player_id))],
        ], className="card"),
    ])


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
            html.Div([html.Button("Ask", id="ask-btn", className="primary")],
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
