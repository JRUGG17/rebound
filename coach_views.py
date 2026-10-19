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
from data.week_cards import card_for

CATEGORY_ORDER = ("technical", "tactical", "physical", "psychological")

RUNG_LABELS = {
    "solo": "solo", "block": "block", "routine": "routine",
    "pattern": "pattern", "conditioned_game": "cond. game", "match": "match",
}


# ------------------------------------------------------------------ today

def week_card(coach_id: str, saved_msg: str | None = None,
              editing: bool = False):
    """What this week is, and the card to walk on court with.

    The card starts from the curriculum deck and is editable, because a week
    is planned by a coach and the deck is where that planning starts, not
    where it ends.
    """
    week = db.ensure_week(clock.today_iso())
    card = week_plan(week) or card_for(
        week["theme_shot"] if week else None,
        week["theme_name"] if week else "")

    options = [{"label": f"{s.title()} Week", "value": s} for s in db.SHOTS] + [
        {"label": "Reset Week", "value": "reset"},
        {"label": "Attacking Week", "value": "attacking"},
        {"label": "Positional Driving Week", "value": "positional"},
    ]

    head = html.Div([
        html.Div([
            html.Div("This week", className="label"),
            html.Div(week["theme_name"] if week else "No week set",
                     className="week-title"),
            html.Div(f"Week {week['id']} of 12 · from "
                     f"{_date.fromisoformat(week['starts_on']).strftime('%-d %b')}"
                     if week else "", className="hint"),
        ]),
        html.Div([
            dcc.Dropdown(id="theme-pick", options=options,
                         value=week["theme_shot"] if week else None,
                         clearable=False, style={"width": "220px"}),
            html.Button("Change", id="set-theme", className="ghost"),
            html.Button("Edit the card", id="edit-plan", className="ghost"),
            html.Span(saved_msg or "", className="hint"),
        ], className="composer-row", style={"margin": 0}),
    ], className="week-head")

    if editing:
        return html.Div([head, html.Div([
            html.Div("One line each. Blank lines are ignored.", className="hint"),
            html.Div([
                html.Div([
                    html.Div("Session", className="label"),
                    dcc.Textarea(id="plan-work", value=_plan_text(card, "work"),
                                 style={"height": "150px"}),
                ], className="week-col"),
                html.Div([
                    html.Div("Shot targets", className="label"),
                    dcc.Textarea(id="plan-targets",
                                 value="\n".join(card["targets"]),
                                 style={"height": "150px"}),
                    html.Div("Technique keys", className="label"),
                    dcc.Textarea(id="plan-keys", value="\n".join(card["keys"]),
                                 style={"height": "150px"}),
                ], className="week-col"),
            ], className="week-cols"),
            html.Div([
                html.Button("Save the week", id="save-plan", className="primary"),
                html.Button("Cancel", id="cancel-plan", className="ghost"),
            ], className="composer-row"),
        ], className="composer")], className="card week-card")

    if not card:
        return html.Div([head], className="card week-card")

    # Laid out like the curriculum slide: the session down the left, the
    # week's themes down the right.
    left = [html.Div("Warmup", className="stage"),
            html.Div("Sort", className="stage")] if card["sort"] else []
    if card["sort"]:
        left.append(html.Ol([html.Li(s) for s in card["sort"]]))
    for stage, drills in card["work"]:
        left.append(html.Div(stage, className="stage"))
        left.append(html.Ol([html.Li(d) for d in drills]))
    left.append(html.Div("Stretchdown", className="stage"))

    right = []
    if card["targets"]:
        right.append(html.Div("Shot targets", className="theme-label"))
        right.append(html.Ol([html.Li(x) for x in card["targets"]]))
    if card["keys"]:
        right.append(html.Div("Technique keys", className="theme-label"))
        right.append(html.Ol([html.Li(x) for x in card["keys"]]))

    columns = [html.Div(left, className="week-col"),
               html.Div(right, className="week-col themes")]

    return html.Div([head, html.Div(columns, className="week-cols")],
                    className="card week-card")


def _plan_text(card: dict, key: str) -> str:
    if key == "work":
        return "\n".join(f"{stage}: {d}" for stage, drills in card["work"]
                          for d in drills)
    return "\n".join(card.get(key, []))


def week_plan(week) -> dict | None:
    """A coach's own version of this week's card, if they have written one."""
    import json

    if not week:
        return None
    raw = db.get_setting(f"plan:{week['id']}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def save_week_plan(week, work: str, targets: str, keys: str) -> None:
    import json

    lines = [ln.strip() for ln in (work or "").splitlines() if ln.strip()]
    grouped: list = []
    for line in lines:
        stage, _, drill = line.partition(":")
        stage = stage.strip() or "Work"
        drill = drill.strip() or stage
        if grouped and grouped[-1][0] == stage:
            grouped[-1][1].append(drill)
        else:
            grouped.append([stage, [drill]])
    plan = {
        "title": week["theme_name"],
        "sort": (week_plan(week) or {}).get("sort", []),
        "work": [(s, d) for s, d in grouped],
        "targets": [x.strip() for x in (targets or "").splitlines() if x.strip()],
        "keys": [x.strip() for x in (keys or "").splitlines() if x.strip()],
    }
    db.set_setting(f"plan:{week['id']}", json.dumps(plan))


def squad_card():
    """What most of the squad is working on — the two minutes on the bleachers."""
    overview = analysis.squad_overview()
    total = overview["total"]

    if not overview["shared"]:
        inner = [html.Div("No cue is shared across the squad this week — feedback is "
                          "individual.", className="empty")]
    else:
        top = overview["shared"][0]
        inner = [
            html.Div([
                html.Div(top["canonical"], className="lead-cue"),
                html.Div(f"{len(top['players'])} of {total} players have had this on "
                         f"court this week", className="hint"),
            ], className="lead-box"),
            *[html.Div([
                html.Span(f"{len(s['players'])}/{total}", className="count-pill"),
                html.Span(s["canonical"], className="shared-cue"),
                html.Span(", ".join(s["players"]), className="hint"),
            ], className="shared-row") for s in overview["shared"][1:]],
            ]
    return html.Div([html.H2("Lead the group with"), *inner], className="card")


def attention_card(coach_id: str):
    """The short list of things actually waiting on this coach."""
    pending = db.pending_approval(coach_id)
    overview = analysis.squad_overview()
    chronic = [p for p in overview["players"] if p["chronic"]]
    stale = [p for p in overview["players"] if not p["entries_this_week"]]

    rows = []
    if pending:
        rows.append(html.Div([
            html.Span(str(len(pending)), className="count-pill"),
            html.Span("written, not sent", className="shared-cue"),
            html.Span(", ".join(sorted({db.person(e["player_id"])["name"].split()[0]
                                        for e in pending})), className="hint"),
        ], className="shared-row"))
    if chronic:
        rows.append(html.Div([
            html.Span(str(len(chronic)), className="count-pill"),
            html.Span("stuck on the same cue", className="shared-cue"),
            html.Span(", ".join(p["name"].split()[0] for p in chronic),
                      className="hint"),
        ], className="shared-row"))
    if stale:
        rows.append(html.Div([
            html.Span(str(len(stale)), className="count-pill"),
            html.Span("nothing logged this week", className="shared-cue"),
            html.Span(", ".join(p["name"].split()[0] for p in stale),
                      className="hint"),
        ], className="shared-row"))
    if not rows:
        rows = [html.Div("Nothing waiting.", className="empty")]
    return html.Div([html.H2("Needs you"), *rows], className="card")


def coach_today(coach_id: str, theme_msg: str | None = None,
                plan_edit: bool = False):
    mine = analysis.my_players(coach_id)
    lessons = sum(p["lessons"] for p in mine)
    return html.Div([
        week_card(coach_id, theme_msg, plan_edit),
        html.Div([
            html.Div([
                html.Div("My lessons", className="label"),
                html.Div(f"{_plural(lessons, 'lesson', 'lessons')} with "
                         f"{_plural(len(mine), 'player', 'players')}",
                         className="hint"),
            ]),
            html.Button("Open my lessons", id="open-lessons", className="primary"),
        ], className="card row-card"),
        html.Div([squad_card(), attention_card(coach_id)], className="two-col"),
    ])


def roster(query: str | None = None, adding: bool = False,
           added: str | None = None):
    """Players, searchable. A club has more than six."""
    overview = analysis.squad_overview()
    needle = (query or "").strip().lower()
    people = [p for p in overview["players"]
              if not needle or needle in p["name"].lower()
              or needle in (p["focus"] or "").lower()]

    rows = []
    for player in people:
        flags = []
        if player["chronic"]:
            run = player["chronic"][0]
            flags.append(html.Span(f"stuck · {run.canonical}", className="tag chronic"))
        if not player["entries_this_week"]:
            flags.append(html.Span("quiet this week", className="tag"))
        rows.append(html.Button([
            html.Div([
                html.Span(player["name"], className="roster-name"),
                html.Span(f"age {player['age']}", className="hint"),
            ]),
            html.Div(player["focus"] or "No focus set", className="roster-focus"),
            html.Div(flags or [html.Span("on track", className="hint")]),
        ], id={"type": "open-player", "id": player["id"]}, className="roster-row"))

    return html.Div([
        html.Div([
            html.H2("Players"),
            html.Div([
                dcc.Input(id="player-search", value=query or "", debounce=False,
                          placeholder="Search by name or focus", className="search"),
                html.Button("+ Add player", id="add-player-open", className="ghost"),
            ], style={"display": "flex", "gap": "8px"}),
        ], className="card-head"),
        html.Div([
            html.Div("New player", className="label"),
            html.Div([
                dcc.Input(id="new-player-name", placeholder="Full name",
                          className="search"),
                dcc.Input(id="new-player-age", type="number", min=5, max=21,
                          placeholder="Age", className="search",
                          style={"width": "90px"}),
                html.Button("Add", id="add-player", className="primary"),
                html.Span(added or "", className="hint"),
            ], className="composer-row"),
        ], className="card") if adding else html.Span(),
        html.Div(rows if rows else [html.Div("Nobody matches that.",
                                             className="empty")], className="roster"),
    ], className="card")


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
                  focus_msg: str | None = None, focus_edit: str | None = None,
                  focus_hist: str | None = None, can_remove: bool = False):
    """A player's page, written for a coach standing next to a court.

    The question it answers is "what should I be watching for", not "what is
    on file". Focus, the last thing they were told, what the coaches keep
    saying, what the player keeps saying — then the heavier things below.
    """
    g = analysis.glance(player_id)
    person = g["person"]

    tiles = []
    if g["from_coaches"]:
        tiles.append(html.Div([
            html.Div("Coaches keep saying", className="label"),
            *[html.Div([html.Span(c["cue"], className="glance-cue"),
                        html.Span(f"×{c['count']}", className="count-pill")],
                       className="glance-row") for c in g["from_coaches"]],
        ], className="card"))
    if g["from_player"]:
        tiles.append(html.Div([
            html.Div(f"{person['name'].split()[0]} keeps saying", className="label"),
            *[html.Div([html.Span(c["cue"], className="glance-cue"),
                        html.Span(f"×{c['count']}", className="count-pill")],
                       className="glance-row") for c in g["from_player"]],
        ], className="card"))

    head = [
        html.Div([
            html.Button("‹ All players", id="back-roster", className="ghost"),
            html.Div([
                html.Span(person["name"], className="profile-name"),
                html.Span(f"age {person['age']}", className="hint"),
            ]),
            html.Div([
                html.Button("Lessons →", id="player-lessons", className="ghost"),
                html.Button("Remove", id="remove-player", className="link danger")
                if can_remove else html.Span(),
            ], style={"display": "flex", "gap": "10px", "alignItems": "center"}),
        ], className="card-head"),
        focus_pair(player_id, "coach", focus_msg, focus_edit, focus_hist),
    ]

    if g["stuck"]:
        run = g["stuck"][0]
        head.append(html.Div([
            html.Strong("Stuck. "),
            f"{run.canonical} has come back {run.count} times across "
            f"{run.span_weeks} weeks and has not moved up the ladder.",
        ], className="timing-box"))

    if g["latest"]:
        head.append(html.Div([
            html.Div("Last thing they were told", className="label"),
            html.Div(g["latest"]["raw_text"], className="body"),
            html.Div(f"{db.person(g['latest']['author_id'])['name']} · "
                     f"{g['latest']['occurred_on']}", className="byline"),
        ], className="card"))

    if running:
        findings = [html.Span(className="spinner"),
                    html.Span("  Reading every coach's notes…", className="hint")]
    elif review:
        findings = ([finding_card(f) for f in review["findings"]]
                    or [html.Div("Nothing to flag.", className="empty")])
    else:
        findings = [html.Div("Not run yet — this one costs a model call.",
                             className="empty")]

    return html.Div([
        *head,
        html.Div(tiles, className="two-col") if tiles else html.Span(),

        html.Div([
            html.Div([html.H2("What no single coach can see"),
                      html.Button("Run comparison", id="run-comparison",
                                  className="primary")], className="card-head"),
            html.Div(findings),
        ], className="card"),
        by_coach(player_id),
    ])


def by_coach(player_id: str):
    """What each coach has said, grouped by who said it.

    A player is coached by several people who rarely compare notes, so the
    useful question is not "what is on file" but "what does each of them
    think". Grouping by author is what makes a disagreement visible.
    """
    rows = db.entries_for_coach(player_id)
    buckets: dict[str, list] = {}
    for entry in rows:
        if entry["author_role"] != "coach":
            continue
        buckets.setdefault(entry["author_id"], []).append(entry)
    if not buckets:
        return html.Span()

    cards = []
    for coach_id, entries in sorted(
            buckets.items(), key=lambda kv: -len(kv[1])):
        coach = db.person(coach_id)
        latest = entries[-3:][::-1]
        cards.append(html.Details([
            html.Summary([
                html.Div([
                    html.Span(coach["name"], className="roster-name"),
                    html.Span(f"{_plural(len(entries), 'note', 'notes')}",
                              className="hint"),
                ]),
                html.Span(f"last {entries[-1]['occurred_on']}", className="hint"),
            ]),
            html.Div([html.Div([
                html.Div(" · ".join(filter(None, [
                    e["occurred_on"], e["setting"],
                    e["rung"].replace("_", " ") if e["rung"] else None])),
                    className="meta"),
                html.Div(e["raw_text"], className="body"),
            ], className="entry from-coach") for e in latest],
                className="bucket-body"),
        ], className="bucket", open=(coach_id == max(buckets, key=lambda k: len(buckets[k])))))

    return html.Div([
        html.H2("What each coach says"),
        html.Div("Grouped by who wrote it, because that is where the disagreements "
                 "show.", className="hint", style={"marginBottom": "10px"}),
        *cards,
    ], className="card")


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
    """A guardian's read-only view, organised the way the rest of the app is.

    Same shape as what a coach sees — the focuses, the lessons, the rest —
    minus anything the child kept private. Grouped by month rather than
    poured onto one page, because a term is a lot of notes and a parent is
    looking for a thread, not a feed.
    """
    parent = db.person(parent_id)
    child_id = parent["child_id"]
    child = db.person(child_id)
    entries = [e for e in db.entries_for_parent(child_id)
               if db.render_for(e, "parent") is not None]

    lessons = [e for e in entries if e["setting"] == "lesson"]
    rest = [e for e in entries if e["setting"] != "lesson"]

    def grouped(rows, empty_text):
        if not rows:
            return [html.Div(empty_text, className="empty")]
        months = analysis.by_month(
            [{"e": r, "on": r["occurred_on"]} for r in rows], lambda i: i["on"])
        blocks = []
        for month, items in months:
            blocks.append(html.Details([
                html.Summary([
                    html.Span(month, className="month-name"),
                    html.Span(_plural(len(items), "note", "notes"),
                              className="hint"),
                ]),
                html.Div([html.Div([
                    html.Div([
                        html.Span(i["e"]["occurred_on"], className="hint"),
                        html.Span("coach" if i["e"]["author_role"] == "coach"
                                  else child["name"].split()[0],
                                  className=f"who-chip "
                                  f"{'coach' if i['e']['author_role'] == 'coach' else 'player'}"),
                        html.Span(i["e"]["setting"], className="tag"),
                    ], className="meta"),
                    html.Div(db.render_for(i["e"], "parent"), className="body"),
                    html.Div(f"— {db.person(i['e']['author_id'])['name']}",
                             className="byline"),
                ], className=f"entry from-"
                   f"{'coach' if i['e']['author_role'] == 'coach' else 'player'}")
                    for i in sorted(items, key=lambda x: x["on"], reverse=True)],
                    className="bucket-body"),
            ], className="bucket month", open=(month == months[0][0])))
        return blocks

    coach_focus = db.current_focus(child_id, "coach")
    own_focus = db.current_focus(child_id, "player")

    return html.Div([
        html.Div([
            html.Div([
                html.Span(child["name"], className="profile-name"),
                html.Span(f"age {child['age']}", className="hint"),
            ]),
            html.Span("Read only", className="tag"),
        ], className="card card-head"),

        html.Div([
            html.Div([
                html.Div("Coach focus", className="label"),
                html.Div(coach_focus["text"] if coach_focus else "Nothing set",
                         className="focus-text" if coach_focus else "empty"),
                html.Div(f"{db.person(coach_focus['coach_id'])['name']} · "
                         f"{coach_focus['set_on']}" if coach_focus else "",
                         className="byline"),
            ], className="card focus-card"),
            html.Div([
                html.Div(f"{child['name'].split()[0]}'s own focus", className="label"),
                html.Div(own_focus["text"] if own_focus else "Nothing set",
                         className="focus-text" if own_focus else "empty"),
            ], className="card focus-card"),
        ], className="two-col focus-pair"),

        html.Div([html.H2(f"Lessons · {len(lessons)}"),
                  *grouped(lessons, "No lessons yet.")], className="card"),
        html.Div([html.H2(f"Everything else · {len(rest)}"),
                  *grouped(rest, "Nothing yet.")], className="card"),

    ])


# ------------------------------------------------------------------ writing

SESSION_KINDS = [("lesson", "Lesson"), ("squad", "Squad"), ("solo", "Solo"),
                 ("tournament", "Match play"), ("reflection", "Other")]


def session_picker(selected: str | None):
    """What kind of session this was.

    Typing into one undifferentiated box is how a diary becomes a pile. One
    tap before writing is the difference between a record you can sort and a
    wall of text — and it means the Organizer is told rather than guessing.
    """
    chosen = selected or "squad"
    return html.Div([
        html.Button(label, id={"type": "kind", "k": key},
                    className=f"chip{' on' if key == chosen else ''}")
        for key, label in SESSION_KINDS
    ], className="chips")


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
                         clearable=False, style={"width": "240px"}),
            dcc.Dropdown(id="note-setting",
                         options=[{"label": label, "value": key}
                                  for key, label in SETTINGS],
                         value=draft.get("setting", "lesson"), clearable=False,
                         style={"width": "180px"}),
            # Coaches write up a lesson on the way home, or the next morning.
            # It belongs on the day it happened.
            dcc.DatePickerSingle(
                id="note-date",
                date=draft.get("on") or clock.today_iso(),
                max_date_allowed=clock.today_iso(),
                min_date_allowed=clock.BLOCK_START.isoformat(),
                display_format="D MMM YYYY"),
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
            html.Div("Write it however you write. It gets filed against the "
                     "curriculum automatically, and the player reads your words, not "
                     "a rewrite of them — but nothing reaches them until you send it.",
                     className="tiein"),
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


FILTERS = [("", "Everything"), ("lesson", "Lessons"), ("squad", "Squad"),
           ("solo", "Solo"), ("tournament", "Match play"),
           ("reflection", "Reflections")]


def recap_panel(player_id: str, viewer_role: str, range_key: str,
                result: dict | None, running: bool, show_entries: bool = False,
                setting: str | None = None, author: str | None = None):
    start, end, label = range_bounds(range_key)
    stats = analysis.period_stats(
        player_id, start, end,
        viewer="player" if viewer_role == "player" else "coach",
        setting=setting or None, author=author or None)
    all_rows = stats["rows"]

    authors = sorted({e["author_id"] for e in
                      (db.entries_for_player(player_id) if viewer_role == "player"
                       else db.entries_for_coach(player_id))})
    author_options = [{"label": "Anyone", "value": ""}] + [
        {"label": db.person(a)["name"], "value": a} for a in authors if db.person(a)]

    filters = html.Div([
        html.Div([
            html.Button(label, id={"type": "filter-setting", "s": key},
                        className=f"chip{' on' if (setting or '') == key else ''}")
            for key, label in FILTERS
        ], className="chips"),
        dcc.Dropdown(id="filter-author", options=author_options,
                     value=author or "", clearable=False,
                     style={"width": "190px"}),
    ], className="filter-row")

    picker = html.Div([
        html.Button(label_, id={"type": "recap-range", "k": key},
                    className=f"tab-btn{' active' if key == range_key else ''}")
        for key, label_ in RANGES
    ], className="tab-row")

    narrowed = []
    if setting:
        narrowed.append(dict(FILTERS).get(setting, setting).lower())
    if author and db.person(author):
        narrowed.append(f"by {db.person(author)['name']}")
    scope = f"{label}, {' · '.join(narrowed)}" if narrowed else label

    tiles = html.Div([
        html.Button([html.Div("Entries", className="label"),
                     html.Div(str(stats["total"]), className="value"),
                     html.Div("hide" if show_entries else "see them",
                              className="sub")],
                    id="toggle-entries", className="stat stat-button"),
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

    raw = []
    if show_entries:
        rows = sorted(all_rows, key=lambda e: e["occurred_on"], reverse=True)
        raw = [html.Div([
            html.Div("Every entry in this stretch, newest first",
                     className="label"),
            *[html.Div([
                html.Div([
                    html.Span(e["occurred_on"], className="hint"),
                    html.Span("coach" if e["author_role"] == "coach" else "you",
                              className=f"who-chip "
                              f"{'coach' if e['author_role'] == 'coach' else 'player'}"),
                    html.Span(e["setting"], className="tag"),
                    html.Span(e["rung"].replace("_", " "), className="tag")
                    if e["rung"] else html.Span(),
                ], className="meta"),
                html.Div(db.render_for(e, viewer_role) or db.agent_text(e),
                         className="body"),
            ], className=f"entry from-"
               f"{'coach' if e['author_role'] == 'coach' else 'player'}")
              for e in rows],
        ], className="card")]

    return html.Div([
        html.Div([
            html.Div([
                html.H2(f"Recap · {scope}"),
                html.Button("Read it back", id="run-recap", className="primary"),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center"}),
            picker,
            filters,
            tiles,
            html.Div(body, style={"marginTop": "6px"}),
        ], className="card"),
        *raw,
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


def coach_lesson_picker(coach_id: str):
    """Whose lessons. Only the players this coach teaches, and nothing else."""
    mine = analysis.my_players(coach_id)
    if not mine:
        return html.Div([
            html.H2("My lessons"),
            html.Div("You have not written up a lesson yet. Start one from a "
                     "player's page.", className="empty"),
        ], className="card")

    rows = [html.Button([
        html.Div([
            html.Span(p["name"], className="roster-name"),
            html.Span(f"age {p['age']}", className="hint"),
        ]),
        html.Div(p["focus"] or "No focus set", className="roster-focus"),
        html.Div(f"{_plural(p['lessons'], 'lesson', 'lessons')} · "
                 f"last {_date.fromisoformat(p['last_on']).strftime('%-d %b')}",
                 className="hint"),
    ], id={"type": "open-player", "id": p["id"]}, className="roster-row")
        for p in mine]

    return html.Div([
        html.H2("My lessons"),
        html.Div(rows, className="roster"),
    ], className="card")


def lesson_months(player_id: str, coach_id: str | None, viewer_role: str,
                  open_month: str | None, year: int | None,
                  open_on: str | None, saving: bool, editing: int | None = None):
    """A player's lessons, by month, newest first.

    A year is about fifty lessons and a career is several hundred, so they
    collapse into months and the months collapse into a year. Twelve months
    fit on a screen; anything older is a year away rather than a scroll.
    """
    items = analysis.lessons(player_id, viewer="player" if viewer_role == "player"
                             else "coach")
    if coach_id:
        items = [i for i in items
                 if any(e["author_id"] == coach_id for e in i["coach"])] or items

    years = sorted({i["on"][:4] for i in items}, reverse=True)
    chosen_year = str(year) if year else (years[0] if years else None)
    in_year = [i for i in items if i["on"].startswith(chosen_year or "")]

    buckets: dict[str, list] = {}
    for lesson in in_year:
        buckets.setdefault(lesson["on"][:7], []).append(lesson)
    months = sorted(buckets.items(), reverse=True)
    current = open_month or (months[0][0] if months else None)

    blocks = []
    for month, lessons in months:
        label = _date.fromisoformat(month + "-01").strftime("%B")
        blocks.append(html.Details([
            html.Summary([
                html.Span(label, className="month-name"),
                html.Span(_plural(len(lessons), "lesson", "lessons"),
                          className="hint"),
            ]),
            html.Div([
                html.Button([
                    html.Span(_date.fromisoformat(l["on"]).strftime("%a %-d"),
                              className="lesson-day"),
                    html.Span(l["week"]["theme_name"] if l["week"] else "",
                              className="tag"),
                    html.Span(f"{len(l['coach'])} coach · {len(l['player'])} player",
                              className="hint"),
                ], id={"type": "open-lesson", "d": l["on"]},
                    className=f"lesson-row{' active' if l['on'] == open_on else ''}")
                for l in lessons
            ], className="bucket-body"),
        ], className="bucket month", open=(month == current)))

    header = [
        html.Div([
            html.Button("‹ Players", id="lessons-back", className="ghost"),
            html.Div([
                html.Span(db.person(player_id)["name"], className="profile-name"),
                html.Span(_plural(len(items), "lesson", "lessons"), className="hint"),
            ]),
            dcc.Dropdown(id="lesson-year",
                         options=[{"label": y, "value": int(y)} for y in years],
                         value=int(chosen_year) if chosen_year else None,
                         clearable=False, style={"width": "110px"}),
        ], className="card-head"),
    ]
    if viewer_role == "coach":
        header.append(html.Button("Write up a lesson", id="goto-note",
                                  className="primary"))

    return html.Div([
        html.Div(header, className="card"),
        html.Div(blocks or [html.Div("No lessons this year.", className="empty")],
                 className="card"),
        lesson_detail(player_id, open_on, viewer_role, saving, editing) if open_on
        else html.Span(),
    ])


def lesson_detail(player_id: str, day: str, viewer_role: str, saving: bool,
                  editing: int | None = None):
    """One lesson: the coach's side and the player's side.

    Editing happens in place — the entry becomes a box with its own text in
    it, because the alternative is retyping something you can see.
    """
    items = analysis.lessons(player_id, viewer="player" if viewer_role == "player"
                             else "coach")
    lesson = next((i for i in items if i["on"] == day), None)
    if not lesson:
        return html.Span()

    def side(entries, who, editable):
        blocks = []
        for entry in entries:
            text = db.render_for(entry, viewer_role)
            if text is None:
                continue
            head = [
                html.Span(who, className=f"who-chip {who}"),
                html.Span(db.person(entry["author_id"])["name"], className="hint"),
            ]
            if editable and entry["id"] != editing:
                head.append(html.Button(
                    "Edit", id={"type": "edit-entry", "i": entry["id"]},
                    className="link"))
            if entry["id"] == editing:
                body = html.Div([
                    dcc.Textarea(id={"type": "edit-text", "i": entry["id"]},
                                 value=entry["raw_text"]),
                    html.Div([
                        html.Button("Save", id={"type": "edit-save", "i": entry["id"]},
                                    className="primary"),
                        html.Button("Cancel", id="edit-cancel", className="ghost"),
                    ], className="composer-row"),
                ], className="composer")
            else:
                body = html.Div(text, className="body")
            blocks.append(html.Div([html.Div(head, className="meta"), body],
                                   className=f"entry from-{who}"))
        return blocks

    coach_side = side(lesson["coach"], "coach", viewer_role == "coach")
    player_side = side(lesson["player"], "player", viewer_role == "player")

    composer_id = "lesson-add"
    add = html.Div([
        dcc.Textarea(id={"type": composer_id, "d": day}),
        html.Div([
            html.Button("🎤", id={"type": "lesson-mic", "d": day}, className="mic"),
            html.Button("Add", id={"type": "lesson-save", "d": day},
                        className="primary"),
            html.Span([html.Span(className="spinner"),
                       html.Span("  Filing it…", className="hint")] if saving else ""),
        ], className="composer-row"),
    ], className="composer")

    return html.Div([
        html.Div([
            html.H2(_date.fromisoformat(day).strftime("%A %-d %B %Y")),
            html.Div(lesson["week"]["theme_name"] if lesson["week"] else "",
                     className="tag"),
        ], className="card-head"),
        html.Div([
            html.Div([
                html.Div("Coach", className="label"),
                *(coach_side or [html.Div("Nothing written.", className="empty")]),
            ], className="card"),
            html.Div([
                html.Div("Player", className="label"),
                *(player_side or [html.Div("Nothing written.", className="empty")]),
            ], className="card"),
        ], className="two-col"),
        html.Div([html.Div("Add to this lesson", className="label"), add],
                 className="card"),
    ], className="lesson-detail")



def focus_pair(player_id: str, viewer_role: str, saved: str | None = None,
               editing: str | None = None, history: str | None = None):
    """This week's two focuses. The coach's, and the player's own.

    The box to change one only appears when you ask for it — an always-open
    text field reads like something you have forgotten to fill in. Past
    focuses live behind the heading rather than stacked underneath, because
    the current one is the thing you came to read.
    """
    week = db.week_of(clock.today_iso())
    coach_focus = db.current_focus(player_id, "coach")
    own_focus = db.current_focus(player_id, "player")
    first = db.person(player_id)["name"].split()[0]

    def panel(focus, title, can_edit, prefix):
        who = db.person(focus["coach_id"]) if focus else None
        body = [
            html.Div([
                html.Span(title, className="label"),
                html.Button("history", id=f"{prefix}-history", className="link"),
            ], className="focus-head"),
            html.Div(focus["text"] if focus else "Nothing set for this week",
                     className="focus-text" if focus else "empty"),
        ]
        if focus:
            stamp = focus["set_on"]
            if who and who["id"] != player_id:
                stamp = f"{who['name']} · {stamp}"
            body.append(html.Div(stamp, className="byline"))

        if can_edit and editing == prefix:
            body += [
                dcc.Textarea(id=f"{prefix}-focus-text",
                             value=focus["text"] if focus else ""),
                html.Div([
                    dcc.Dropdown(id=f"{prefix}-focus-category",
                                 options=[{"label": c.title(), "value": c}
                                          for c in CATEGORY_ORDER],
                                 value=focus["category"] if focus else "technical",
                                 clearable=False, style={"width": "150px"}),
                    html.Button("Set for this week", id=f"{prefix}-set-focus",
                                className="primary"),
                    html.Button("Cancel", id=f"{prefix}-cancel", className="ghost"),
                ], className="composer-row"),
            ]
        elif can_edit:
            body.append(html.Div([
                html.Button("Change focus", id=f"{prefix}-change",
                            className="ghost"),
                html.Span(saved or "", className="hint"),
            ], className="composer-row"))

        if history == prefix:
            rows = db.focus_history(player_id, prefix if prefix == "coach" else "player")
            past = [html.Div([
                html.Div(f["set_on"]
                         + (f" – {f['resolved_on']}" if f["resolved_on"]
                            else " – now"), className="hint"),
                html.Div(f["text"], className="body"),
            ], className="entry") for f in rows[:12]]
            body.append(html.Div(
                [html.Div("Earlier focuses", className="label")]
                + (past or [html.Div("Nothing earlier.", className="empty")]),
                className="focus-history"))
        return html.Div(body, className="card focus-card")

    label = (f"Coach focus · {week['theme_name']}"
             if week and week["theme_shot"] else "Coach focus · this week")
    return html.Div([
        panel(coach_focus, label, viewer_role in ("coach", "admin"), "coach"),
        panel(own_focus, f"{first}'s own focus" if viewer_role != "player"
              else "My own focus", viewer_role == "player", "own"),
    ], className="two-col focus-pair")
