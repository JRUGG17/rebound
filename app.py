"""Rebound — a shared training diary for a junior squash academy.

Run:  ./venv/bin/python app.py     then open http://127.0.0.1:8050

No login. The "I am…" switcher at the top changes who you are, because the
point of a demo is to see the same week from a coach's side, a kid's side and
a parent's side within about thirty seconds.

Model calls run on a worker thread with a dcc.Interval polling for the result.
A call takes several seconds and a Dash callback that blocks for that long
freezes the page.
"""

from __future__ import annotations

import threading
import uuid

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

import coach_views as cv
from core import aio, analysis, clock, db, metering
from core import playbook as pb
from core.agents import comparison, methodology, organizer, recap as recap_agent
from core.config import MODEL_NAME, key_is_set
from data import seed

# ---------------------------------------------------------------- jobs

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _run_job(fn) -> str:
    """Start `fn` on a worker thread and return a handle to poll."""
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {"state": "running"}

    def work() -> None:
        try:
            result = fn()
            with _JOBS_LOCK:
                _JOBS[job_id] = {"state": "done", "result": result}
        except Exception as exc:  # noqa: BLE001 — shown to the user, not swallowed
            with _JOBS_LOCK:
                _JOBS[job_id] = {"state": "error", "message": str(exc)[:240]}

    threading.Thread(target=work, daemon=True).start()
    return job_id


def clicked(*counts) -> bool:
    """Did a person actually press something?

    Dash fires a callback when one of its Input components is newly mounted,
    with n_clicks of None — and ctx.triggered_id names that button as though
    it had been pressed. Any callback that writes to the database has to check
    the count, not the trigger, or it runs the moment its button appears.

    This has now caused two real bugs: a save throwing the user out of the
    private tab, and a coach's note being sent to a player the instant the
    send button rendered, before they had read it. Guard every one.
    """
    return any(bool(c) for c in counts)


def job(job_id: str | None) -> dict:
    if not job_id:
        return {"state": "idle"}
    with _JOBS_LOCK:
        return dict(_JOBS.get(job_id, {"state": "idle"}))


def save_reflection(player_id: str, text: str, visibility: str,
                    kind: str = "squad"):
    def work():
        on = clock.today_iso()
        organized, _usage = aio.run(
            organizer.organize_player_entry(player_id, text, on))
        db.add_entry(
            player_id=player_id, author_id=player_id, author_role="player",
            # The player said what kind of session it was. The model only
            # guesses when nobody told it.
            setting=kind or organized.setting, rung=organized.rung, shot=organized.shot,
            category=organized.category, cue_id=organized.cue_id, proposed_cue=organized.proposed_cue,
            raw_text=text, summary=organized.summary, visibility=visibility,
            occurred_on=on,
            flagged_injection=organized.injected_instruction,
            flagged_welfare=organized.welfare_flag,
        )
        return {"ok": True}
    return _run_job(work)


def file_coach_note(player_id: str, text: str, setting: str, on: str | None = None):
    def work():
        organized, _usage = aio.run(
            organizer.organize_coach_note(player_id, text, on or clock.today_iso()))
        return {"coach_note": organized.model_dump()}
    return _run_job(work)


def run_comparison(player_id: str):
    def work():
        review, _usage = aio.run(comparison.review_player(player_id))
        return review.model_dump()
    return _run_job(work)


def run_recap(player_id: str, start: str, end: str, audience: str,
              setting: str | None = None, author: str | None = None):
    def work():
        output, _usage = aio.run(
            recap_agent.recap_period(player_id, start, end, audience=audience,
                                     setting=setting, author=author))
        return {"recap": output.model_dump() if output else None}
    return _run_job(work)


def run_day_summary(player_id: str, day: str, audience: str):
    def work():
        output, _usage = aio.run(
            recap_agent.summarise_day(player_id, day, audience=audience))
        return {"day": output.model_dump() if output else None}
    return _run_job(work)


def save_dated(player_id: str, text: str, visibility: str, day: str,
               setting: str | None = None):
    def work():
        organized, _usage = aio.run(
            organizer.organize_player_entry(player_id, text, day))
        db.add_entry(
            player_id=player_id, author_id=player_id, author_role="player",
            setting=setting or organized.setting,
            rung=organized.rung, shot=organized.shot,
            category=organized.category, cue_id=organized.cue_id, proposed_cue=organized.proposed_cue,
            raw_text=text, summary=organized.summary, visibility=visibility,
            occurred_on=day,
            flagged_injection=organized.injected_instruction,
            flagged_welfare=organized.welfare_flag,
        )
        return {"dated": True}
    return _run_job(work)


def run_lesson_arc(player_id: str, audience: str):
    def work():
        arc, _usage = aio.run(recap_agent.recap_lessons(player_id, audience=audience))
        return {"arc": arc.model_dump() if arc else None}
    return _run_job(work)


def file_lesson_note(player_id: str, coach_id: str, text: str, day: str):
    """A coach adding to a lesson. Filed and released in one step — they are
    writing it to the player, and there is no rewrite to review."""
    def work():
        organized, _usage = aio.run(
            organizer.organize_coach_note(player_id, text, day))
        db.add_entry(
            player_id=player_id, author_id=coach_id, author_role="coach",
            setting="lesson", rung=organized.rung, shot=organized.shot,
            category=organized.category, cue_id=organized.cue_id,
            proposed_cue=organized.proposed_cue, raw_text=text,
            summary=organized.summary, approved_by=coach_id,
            visibility="shared", occurred_on=day,
        )
        return {"lesson_added": True}
    return _run_job(work)


def ask_playbook(question: str):
    def work():
        answer, _usage = aio.run(methodology.ask(question))
        return answer.model_dump()
    return _run_job(work)


# ---------------------------------------------------------------- player views

def entry_card(entry, viewer_role: str):
    text = db.render_for(entry, viewer_role)
    if text is None:
        return None
    author = db.person(entry["author_id"])
    bits = [entry["occurred_on"], entry["setting"]]
    if entry["rung"]:
        bits.append(entry["rung"].replace("_", " "))
    if entry["shot"]:
        bits.append(entry["shot"])

    meta = [html.Span(" · ".join(bits))]
    if entry["category"]:
        meta.append(html.Span(entry["category"], className=f"tag {entry['category']}"))
    if entry["visibility"] == "private":
        meta.append(html.Span("private", className="tag"))

    children = [html.Div(meta, className="meta"), html.Div(text, className="body")]
    if author and author["role"] == "coach":
        children.append(html.Div(f"— {author['name']}", className="byline"))
    return html.Div(children, className="entry")


def player_today(player_id: str):
    """Just who you are and what week it is. The focuses sit under it."""
    player = db.person(player_id)
    week = db.week_of(clock.today_iso())

    return [html.Div([
        html.Div([
            html.Span(player["name"], className="profile-name"),
            html.Span(f"age {player['age']}", className="hint"),
        ]),
        html.Div(html.Span(week["theme_name"], className="theme-pill")
                 if week else "", className="today-week"),
    ], className="card today-head")]


RECENT_ON_TODAY = 4


def player_reflections(player_id: str, tab: str, job_id: str | None,
                       kind: str | None = None):
    """One box, two buttons.

    This used to be two tabs, Shared and Just me. The tab is gone and the
    choice is not: a private space is worth having, but it is not worth a
    whole second screen for something a player uses occasionally. More to the
    point, the value of being able to keep something back is mostly in what
    it does to everything else — a player who knows every word reaches their
    coach writes more carefully in the shared box too.

    So: write, then choose where it goes. Private entries appear in the same
    list with a lock on them, because it is one journal.
    """
    entries = list(reversed(db.entries_for_player(player_id)))
    shown = entries[:RECENT_ON_TODAY]
    cards = [c for c in (entry_card(e, "player") for e in shown) if c]
    body = cards or [html.Div("Nothing yet.", className="empty")]
    if len(entries) > len(shown):
        body.append(html.Div(
            f"{len(entries) - len(shown)} older — they are in your journal.",
            className="hint", style={"paddingTop": "12px"}))

    state = job(job_id)
    status = []
    if state["state"] == "running":
        status = [html.Span(className="spinner"),
                  html.Span("  Filing it…", className="hint")]
    elif state["state"] == "error":
        status = [html.Span(f"Could not save that: {state['message']}",
                            className="hint")]

    return html.Div([
        html.Div([
            cv.session_picker(kind),
            dcc.Textarea(id="composer"),
            html.Div([
                html.Button("🎤", id="mic", className="mic", title="Speak instead"),
                html.Button("Save", id="save", className="primary"),
                html.Button("🔒 Keep private", id="save-private", className="tab-btn",
                            title="Your coaches will not see this one"),
                html.Span(status),
            ], className="composer-row"),
            html.Hr(style={"border": 0, "borderTop": "1px solid var(--line)",
                           "margin": "18px 0"}),
            *body,
        ], className="card composer"),
    ])


def usage_page():
    totals = metering.totals()
    rows = metering.ledger_rows()[-30:][::-1]
    stats = [
        ("Model calls", f"{totals['runs']:,}", MODEL_NAME),
        ("Tokens", f"{totals['total_tokens']:,}",
         f"{totals['input_tokens']:,} in / {totals['output_tokens']:,} out"),
        ("Served from cache", f"{totals['cache_hit_rate'] * 100:.0f}%",
         f"{totals['cached_input_tokens']:,} tokens"),
        ("Cost", f"${totals['cost_usd']:.4f}",
         f"at ${metering.PRICE_PER_MTOK_INPUT:.2f}/"
         f"${metering.PRICE_PER_MTOK_CACHED_INPUT:.2f}/"
         f"${metering.PRICE_PER_MTOK_OUTPUT:.2f} per Mtok"),
    ]
    cached_tok = totals["cached_input_tokens"]
    saved = cached_tok * (metering.PRICE_PER_MTOK_INPUT
                          - metering.PRICE_PER_MTOK_CACHED_INPUT) / 1_000_000
    banner = [html.Div(
        f"Caching has saved ${saved:.4f} so far — {cached_tok:,} input tokens served "
        f"at ${metering.PRICE_PER_MTOK_CACHED_INPUT:.2f} per million instead of "
        f"${metering.PRICE_PER_MTOK_INPUT:.2f}. Rates are the published gpt-6-luna "
        f"prices from the course tokenomics lecture.", className="banner")]
    table = html.Table([
        html.Thead(html.Tr([html.Th("When"), html.Th("Agent"),
                            html.Th("In", className="num"),
                            html.Th("Cached", className="num"),
                            html.Th("Out", className="num"),
                            html.Th("Secs", className="num")])),
        html.Tbody([html.Tr([
            html.Td(r["at"][:19].replace("T", " ")), html.Td(r["agent"]),
            html.Td(f"{r['input_tokens']:,}", className="num"),
            html.Td(f"{r['cached_input_tokens']:,}", className="num"),
            html.Td(f"{r['output_tokens']:,}", className="num"),
            html.Td(f"{r['seconds']:.1f}", className="num"),
        ]) for r in rows]),
    ], className="usage")
    return html.Div([
        *banner,
        html.Div([html.Div([html.Div(label, className="label"),
                            html.Div(value, className="value"),
                            html.Div(sub, className="sub")], className="stat")
                  for label, value, sub in stats], className="stat-row"),
        html.Div([html.H2("Every call, newest first"),
                  table if rows else html.Div("No runs yet.", className="empty")],
                 className="card"),
    ])


# ---------------------------------------------------------------- app

app = Dash(__name__, title="Rebound — Squash Tigers",
           suppress_callback_exceptions=True)
server = app.server

ROLE_LABEL = {"player": "Player", "coach": "Coach", "parent": "Parent",
              "admin": "Admin"}


def people_options():
    options = []
    for role in ("player", "coach", "parent", "admin"):
        for person in db.people(role):
            suffix = f" (age {person['age']})" if person["age"] else ""
            options.append({"label": f"{ROLE_LABEL[role]}: {person['name']}{suffix}",
                            "value": person["id"]})
    return options


app.layout = html.Div([
    dcc.Store(id="nav", data="today"),
    dcc.Store(id="sel-player", data=None),
    dcc.Store(id="pb-sec", data=1),
    dcc.Store(id="job", data=None),
    dcc.Store(id="review", data=None),
    dcc.Store(id="answer", data=None),
    # Anything render_page needs to react to has to live up here. It cannot
    # take an Input from a component it is itself responsible for creating.
    dcc.Store(id="theme-tick", data=None),
    dcc.Store(id="draft", data=None),
    dcc.Store(id="recap-range", data="30"),
    dcc.Store(id="recap", data=None),
    dcc.Store(id="cal-offset", data=0),
    dcc.Store(id="sel-day", data=None),
    dcc.Store(id="day-summary", data=None),
    dcc.Store(id="lesson-arc", data=None),
    dcc.Store(id="focus-tick", data=None),
    dcc.Store(id="search", data=""),
    dcc.Store(id="year-sel", data=None),
    dcc.Store(id="open-month", data=None),
    dcc.Store(id="show-entries", data=False),
    dcc.Store(id="recap-year", data=None),
    dcc.Store(id="lesson-query", data=""),
    dcc.Store(id="kind", data="squad"),
    dcc.Store(id="editing", data=None),
    dcc.Store(id="focus-edit", data=None),
    dcc.Store(id="focus-history", data=None),
    dcc.Store(id="f-setting", data=""),
    dcc.Store(id="f-author", data=""),
    dcc.Store(id="adding-player", data=False),
    dcc.Store(id="added-msg", data=None),
    dcc.Store(id="plan-edit", data=False),
    dcc.Interval(id="poll", interval=400, disabled=True),

    html.Div([
        html.Div(["Re", html.Span("bound")], className="brand"),
        html.Label("I am"),
        dcc.Dropdown(id="who", options=people_options(), value="maya",
                     clearable=False, style={"width": "250px"}),
        # roster-changed is bumped whenever somebody is added or removed, so
        # the switcher can rebuild. Without it a new player had no way in.
        dcc.Store(id="roster-changed", data=0),
        html.Div([
            html.Button("‹", id="back-week", className="step", title="Back a week"),
            html.Div(id="today-label", className="today"),
            html.Button("›", id="fwd-week", className="step", title="Forward a week"),
            html.Button("⟲", id="reset-clock", className="step", title="Back to the start"),
        ], className="datebar"),
    ], className="topbar"),

    html.Div([
        html.Div(id="sidebar", className="sidebar"),
        html.Div(id="page", className="page"),
    ], className="shell"),
])


@app.callback(
    Output("today-label", "children"),
    Input("back-week", "n_clicks"), Input("fwd-week", "n_clicks"),
    Input("reset-clock", "n_clicks"), Input("nav", "data"),
    # Setting the shot of the week has to repaint the header too, or it keeps
    # showing last week's theme until you happen to navigate.
    Input("theme-tick", "data"),
)
def move_clock(_b, _f, _r, _nav, _theme):
    if ctx.triggered_id == "back-week":
        clock.shift(-7)
    elif ctx.triggered_id == "fwd-week":
        clock.shift(7)
    elif ctx.triggered_id == "reset-clock":
        clock.reset()
    today = clock.today()
    week = db.week_of(today.isoformat())
    label = today.strftime("%a %d %b %Y")
    if week and week["theme_shot"]:
        return f"{label} · {week['theme_name']}"
    return f"{label} · no week set"


# Five places to stand. Everything else is reached by drilling in from one
# of them, because eleven parallel destinations is how this got lost.
PLAYER_NAV = [
    (None, [("training", "My training"), ("lessons", "My lessons"),
            ("recap", "Recap")]),
    (None, [("usage", "Usage")]),
]
PARENT_NAV = [
    (None, [("training", "Training record")]),
]
COACH_NAV = [
    (None, [("today", "Today"), ("players", "Players"), ("lessons", "My lessons")]),
    (None, [("resources", "Coach resources"), ("usage", "Usage")]),
]


@app.callback(Output("sidebar", "children"), Input("who", "value"), Input("nav", "data"),
              Input("sel-player", "data"))
def render_sidebar(who, nav, sel_player):
    person = db.person(who)
    if person is None:
        return None
    if person["role"] in ("coach", "admin"):
        groups = COACH_NAV
    elif person["role"] == "parent":
        groups = PARENT_NAV
    else:
        groups = PLAYER_NAV

    out = []
    for heading, items in groups:
        if heading:
            out.append(html.Div(heading, className="side-heading"))
        for key, label in items:
            out.append(html.Button(label, id={"type": "nav", "key": key},
                                   className=f"side-btn{' active' if nav == key else ''}"))
    # Whose journal a coach is reading has to be visible, or the Calendar and
    # Recap tabs silently mean a different player than the one they picked.
    if person["role"] in ("coach", "admin") and nav in ("calendar", "recap", "lessons"):
        subject = db.person(sel_player) if sel_player else None
        if subject:
            out.append(html.Div(f"Showing {subject['name']}", className="side-note"))
    return html.Div(out)


@app.callback(Output("nav", "data"), Output("sel-player", "data", allow_duplicate=True),
              Input({"type": "nav", "key": ALL}, "n_clicks"),
              State("nav", "data"), prevent_initial_call=True)
def switch_nav(clicks, current):
    if not ctx.triggered_id or not any(c for c in clicks if c):
        return current, no_update
    return ctx.triggered_id["key"], None


@app.callback(Output("sel-day", "data", allow_duplicate=True),
              Input({"type": "nav", "key": ALL}, "n_clicks"),
              prevent_initial_call=True)
def leave_open_day(clicks):
    # Calendar should mean the calendar. Without this, clicking it while a day
    # was open just re-rendered that day and looked like a dead button.
    if not any(c for c in clicks if c):
        return no_update
    return None


@app.callback(Output("nav", "data", allow_duplicate=True),
              Input("who", "value"), prevent_initial_call=True)
def reset_nav(_who):
    return "today"


@app.callback(Output("sel-player", "data"), Output("review", "data"),
              Input({"type": "open-player", "id": ALL}, "n_clicks"),
              prevent_initial_call=True)
def pick_player(clicks):
    if not any(c for c in clicks if c):
        return no_update, no_update
    return ctx.triggered_id["id"], None


@app.callback(Output("sel-player", "data", allow_duplicate=True),
              Output("review", "data", allow_duplicate=True),
              Input("back-roster", "n_clicks"), prevent_initial_call=True)
def back_to_roster(n):
    return (None, None) if n else (no_update, no_update)


@app.callback(Output("pb-sec", "data"),
              Input({"type": "pb-section", "n": ALL}, "n_clicks"),
              State("pb-sec", "data"), prevent_initial_call=True)
def pick_section(clicks, current):
    if not any(c for c in clicks if c):
        return current
    return ctx.triggered_id["n"]


@app.callback(Output("theme-tick", "data"),
              Input("set-theme", "n_clicks"), State("theme-pick", "value"),
              prevent_initial_call=True)
def set_theme(n, shot):
    if not n or not shot:
        return no_update
    week = db.ensure_week(clock.today_iso())
    names = {"reset": "Reset Week", "attacking": "Attacking Week",
             "positional": "Positional Driving Week"}
    name = names.get(shot, f"{shot.title()} Week")
    with db.connect() as conn:
        conn.execute("UPDATE weeks SET theme_shot = ?, theme_name = ? WHERE id = ?",
                     (None if shot in names else shot, name, week["id"]))
        # A hand-edited card belongs to the shot it was written for. Pick a
        # different shot and you want that shot's standard card back, not
        # last week's edits with a new title on top.
        conn.execute("DELETE FROM settings WHERE key = ?", (f"plan:{week['id']}",))
    return f"Set to {name}."


# --------------------------------------------------- the one async channel

@app.callback(
    Output("job", "data"), Output("poll", "disabled"), Output("composer", "value"),
    Input("save", "n_clicks"), Input("save-private", "n_clicks"),
    State("composer", "value"), State("who", "value"), State("kind", "data"),
    prevent_initial_call=True,
)
def start_save(save_clicks, private_clicks, text, who, kind):
    if not clicked(save_clicks, private_clicks):
        return no_update, no_update, no_update
    person = db.person(who)
    if not text or not text.strip() or not person or person["role"] != "player":
        return no_update, no_update, no_update
    visibility = "private" if ctx.triggered_id == "save-private" else "shared"
    return (save_reflection(who, text.strip(), visibility, kind or "squad"),
            False, "")


@app.callback(
    Output("job", "data", allow_duplicate=True),
    Output("poll", "disabled", allow_duplicate=True),
    Input("run-comparison", "n_clicks"), State("sel-player", "data"),
    prevent_initial_call=True,
)
def start_comparison(n, player_id):
    if not n or not player_id:
        return no_update, no_update
    return run_comparison(player_id), False


@app.callback(
    Output("job", "data", allow_duplicate=True),
    Output("poll", "disabled", allow_duplicate=True),
    Output("ask-box", "value"),
    Input("ask-btn", "n_clicks"), State("ask-box", "value"),
    prevent_initial_call=True,
)
def start_ask(n, question):
    if not n or not question or not question.strip():
        return no_update, no_update, no_update
    return ask_playbook(question.strip()), False, ""


@app.callback(
    Output("poll", "disabled", allow_duplicate=True),
    Output("review", "data", allow_duplicate=True),
    Output("answer", "data", allow_duplicate=True),
    Output("draft", "data", allow_duplicate=True),
    Output("recap", "data", allow_duplicate=True),
    Output("day-summary", "data", allow_duplicate=True),
    Output("lesson-arc", "data", allow_duplicate=True),
    Input("poll", "n_intervals"), State("job", "data"), State("draft", "data"),
    prevent_initial_call=True,
)
def collect(_n, job_id, draft):
    state = job(job_id)
    if state["state"] == "running":
        return False, no_update, no_update, no_update, no_update, no_update, no_update
    result = state.get("result")
    if state["state"] == "done" and isinstance(result, dict):
        if "findings" in result:
            return True, result, no_update, no_update, no_update, no_update, no_update
        if "answer" in result:
            return True, no_update, result, no_update, no_update, no_update, no_update
        if "coach_note" in result and draft:
            return True, no_update, no_update, {**draft, "organized": result["coach_note"]}, no_update, no_update, no_update
        if "recap" in result:
            return True, no_update, no_update, no_update, result["recap"], no_update, no_update
        if "day" in result:
            return True, no_update, no_update, no_update, no_update, result["day"], no_update
        if "arc" in result:
            return True, no_update, no_update, no_update, no_update, no_update, result["arc"]
    return True, no_update, no_update, no_update, no_update, no_update, no_update


# --------------------------------------------------- writing a lesson note

@app.callback(
    Output("job", "data", allow_duplicate=True),
    Output("poll", "disabled", allow_duplicate=True),
    Output("draft", "data", allow_duplicate=True),
    Output("note-text", "value"),
    Input("file-note", "n_clicks"),
    State("note-player", "value"), State("note-text", "value"),
    State("note-setting", "value"), State("note-date", "date"),
    prevent_initial_call=True,
)
def start_file_note(n, player_id, text, setting, on):
    if not n or not player_id or not text or not text.strip():
        return no_update, no_update, no_update, no_update
    draft = {"player_id": player_id, "text": text.strip(),
             "setting": setting or "lesson", "on": on or clock.today_iso(),
             "organized": None}
    return (file_coach_note(player_id, text.strip(), setting or "lesson",
                            draft["on"]), False, draft, "")


@app.callback(
    Output("draft", "data", allow_duplicate=True),
    Input("release-note", "n_clicks"), Input("keep-note", "n_clicks"),
    State("draft", "data"), State("note-player-text", "value"), State("who", "value"),
    prevent_initial_call=True,
)
def save_note(release_clicks, keep_clicks, draft, player_text, coach_id):
    if not clicked(release_clicks, keep_clicks):
        return no_update
    if not draft or not draft.get("organized"):
        return no_update
    trigger = ctx.triggered_id
    release = trigger == "release-note"
    organized = draft["organized"]
    # The note is the coach's words. If they edited them on the way out, the
    # edit is the note — not a second version sitting beside the original.
    text = (player_text or "").strip() or draft["text"]
    db.add_entry(
        player_id=draft["player_id"], author_id=coach_id, author_role="coach",
        setting=draft["setting"], rung=organized.get("rung"),
        shot=organized.get("shot"), category=organized.get("category"),
        cue_id=organized.get("cue_id"), proposed_cue=organized.get("proposed_cue"),
        raw_text=text,
        summary=organized.get("summary"),
        # Releasing is the approval. A note kept back stays a coach record and
        # the player is shown nothing, rather than the coach's raw words.
        approved_by=coach_id if release else None,
        visibility="shared",
        occurred_on=draft.get("on") or clock.today_iso(),
    )
    name = db.person(draft["player_id"])["name"].split()[0]
    if release:
        note = f"Sent to {name}, in your words."
    else:
        note = "Saved as a coach record. Nothing shown to the player."
    return {"saved": note}


@app.callback(Output("recap-range", "data"), Output("recap", "data"),
              Input({"type": "recap-range", "k": ALL}, "n_clicks"),
              State("recap-range", "data"), prevent_initial_call=True)
def pick_range(clicks, current):
    if not any(c for c in clicks if c):
        return current, no_update
    # A recap belongs to the stretch it was written about, so changing the
    # range clears it rather than leaving last week's text above new numbers.
    return ctx.triggered_id["k"], None


@app.callback(
    Output("job", "data", allow_duplicate=True),
    Output("poll", "disabled", allow_duplicate=True),
    Input("run-recap", "n_clicks"),
    State("who", "value"), State("sel-player", "data"), State("recap-range", "data"),
    State("f-setting", "data"), State("f-author", "data"),
    prevent_initial_call=True,
)
def start_recap(n, who, sel_player, range_key, f_setting, f_author):
    person = db.person(who)
    if not clicked(n) or person is None:
        return no_update, no_update
    is_player = person["role"] == "player"
    subject = who if is_player else sel_player
    if not subject:
        return no_update, no_update
    start, end, _label = cv.range_bounds(range_key or "30")
    return (run_recap(subject, start, end, "player" if is_player else "coach",
                      f_setting or None, f_author or None), False)


@app.callback(Output("focus-tick", "data"),
              Output("focus-edit", "data", allow_duplicate=True),
              Input("coach-set-focus", "n_clicks"),
              State("coach-focus-text", "value"),
              State("coach-focus-category", "value"),
              State("sel-player", "data"), State("who", "value"),
              prevent_initial_call=True)
def set_coach_focus(n, text, category, player_id, coach_id):
    person = db.person(coach_id)
    if not clicked(n) or not text or not text.strip() or not player_id:
        return no_update, no_update
    if person is None or person["role"] not in ("coach", "admin"):
        return no_update, no_update
    db.set_focus(player_id, coach_id, text, category, "coach", clock.today_iso())
    return f"Set for this week. {db.person(player_id)['name'].split()[0]} sees it.", None


@app.callback(Output("focus-tick", "data", allow_duplicate=True),
              Output("focus-edit", "data", allow_duplicate=True),
              Input("own-set-focus", "n_clicks"),
              State("own-focus-text", "value"),
              State("own-focus-category", "value"), State("who", "value"),
              prevent_initial_call=True)
def set_own_focus(n, text, category, who):
    person = db.person(who)
    if not clicked(n) or not text or not text.strip():
        return no_update, no_update
    if person is None or person["role"] != "player":
        return no_update, no_update
    db.set_focus(who, who, text, category, "player", clock.today_iso())
    return "Set for this week.", None


@app.callback(
    Output("job", "data", allow_duplicate=True),
    Output("poll", "disabled", allow_duplicate=True),
    Output({"type": "lesson-add", "d": ALL}, "value"),
    Input({"type": "lesson-save", "d": ALL}, "n_clicks"),
    State({"type": "lesson-add", "d": ALL}, "value"),
    State("who", "value"), State("sel-player", "data"),
    prevent_initial_call=True,
)
def add_to_lesson(clicks, texts, who, sel_player):
    """Either side adding to a lesson. This was lost when dead callbacks were
    pruned, which is why a player could not add anything."""
    blank = ["" for _ in texts]
    keep = [no_update for _ in texts]
    if not any(c for c in clicks if c):
        return no_update, no_update, keep
    person = db.person(who)
    if person is None:
        return no_update, no_update, keep
    day = ctx.triggered_id["d"]
    wanted = [i["id"]["d"] for i in ctx.states_list[0]]
    try:
        text = texts[wanted.index(day)]
    except (ValueError, IndexError):
        return no_update, no_update, keep
    if not text or not text.strip():
        return no_update, no_update, keep

    # Empty the box on the way out. Leaving the text sitting there after it
    # has been filed is how you end up posting it twice.
    if person["role"] == "player":
        return (save_dated(who, text.strip(), "shared", day, setting="lesson"),
                False, blank)
    if not sel_player:
        return no_update, no_update, keep
    return file_lesson_note(sel_player, who, text.strip(), day), False, blank


@app.callback(Output("nav", "data", allow_duplicate=True),
              Output("draft", "data", allow_duplicate=True),
              Input("goto-note", "n_clicks"), State("sel-player", "data"),
              prevent_initial_call=True)
def write_up_lesson(n, player_id):
    if not clicked(n) or not player_id:
        return no_update, no_update
    return "note", {"player_id": player_id, "setting": "lesson",
                    "on": clock.today_iso(), "text": "", "organized": None}


@app.callback(Output("search", "data"), Input("player-search", "value"),
              prevent_initial_call=True)
def do_search(value):
    return value or ""


@app.callback(Output("nav", "data", allow_duplicate=True),
              Input("open-lessons", "n_clicks"), prevent_initial_call=True)
def go_to_lessons(n):
    return "lessons" if clicked(n) else no_update


@app.callback(Output("nav", "data", allow_duplicate=True),
              Input("player-lessons", "n_clicks"), prevent_initial_call=True)
def go_to_player_lessons(n):
    return "lessons" if clicked(n) else no_update


@app.callback(Output("sel-player", "data", allow_duplicate=True),
              Input("lessons-back", "n_clicks"), prevent_initial_call=True)
def leave_lessons(n):
    return None if clicked(n) else no_update


@app.callback(Output("year-sel", "data"), Input("lesson-year", "value"),
              prevent_initial_call=True)
def pick_year(value):
    return value


@app.callback(Output("sel-day", "data", allow_duplicate=True),
              Input({"type": "open-lesson", "d": ALL}, "n_clicks"),
              prevent_initial_call=True)
def open_lesson(clicks):
    if not any(c for c in clicks if c):
        return no_update
    return ctx.triggered_id["d"]


@app.callback(Output("recap-year", "data"),
              Input("recap-year-pick", "value"), prevent_initial_call=True)
def pick_recap_year(value):
    """Its own callback with one Input. The dropdown only exists while the
    entries are showing, and a callback that bundles a sometimes-absent
    Input with anything else stops firing for everything."""
    return value


@app.callback(Output("show-entries", "data"),
              Input("toggle-entries", "n_clicks"), State("show-entries", "data"),
              prevent_initial_call=True)
def toggle_entries(n, showing):
    # Reading the entries yourself should not need an agent. The tile is the
    # switch: counts by default, the actual notes if you want them.
    return (not showing) if clicked(n) else no_update


@app.callback(Output("kind", "data"),
              Input({"type": "kind", "k": ALL}, "n_clicks"),
              State("kind", "data"), prevent_initial_call=True)
def pick_kind(clicks, current):
    if not any(c for c in clicks if c):
        return current
    return ctx.triggered_id["k"]


@app.callback(Output("editing", "data"),
              Input({"type": "edit-entry", "i": ALL}, "n_clicks"),
              Input("edit-cancel", "n_clicks"),
              prevent_initial_call=True)
def start_editing(clicks, cancel):
    if ctx.triggered_id == "edit-cancel":
        return None if clicked(cancel) else no_update
    if not any(c for c in clicks if c):
        return no_update
    return ctx.triggered_id["i"]


@app.callback(Output("editing", "data", allow_duplicate=True),
              Input({"type": "edit-save", "i": ALL}, "n_clicks"),
              State({"type": "edit-text", "i": ALL}, "value"),
              State("who", "value"), prevent_initial_call=True)
def save_edit(clicks, texts, who):
    """Edit an entry in place. The author's words replace the author's words —
    no second version, same as everywhere else."""
    if not any(c for c in clicks if c):
        return no_update
    entry_id = ctx.triggered_id["i"]
    wanted = [i["id"]["i"] for i in ctx.states_list[0]]
    try:
        text = texts[wanted.index(entry_id)]
    except (ValueError, IndexError):
        return None
    if text and text.strip():
        with db.connect() as conn:
            conn.execute("UPDATE entries SET raw_text = ? WHERE id = ?",
                         (text.strip(), entry_id))
    return None


# One callback per button. Bundling buttons that live on different render
# states is what broke this: a Dash callback is dead while any of its Inputs
# is missing, and the cancel buttons only exist once you are already editing,
# so the change button could never fire.

@app.callback(Output("focus-edit", "data"),
              Input("coach-change", "n_clicks"), prevent_initial_call=True)
def edit_coach_focus(n):
    return "coach" if clicked(n) else no_update


@app.callback(Output("focus-edit", "data", allow_duplicate=True),
              Input("own-change", "n_clicks"), prevent_initial_call=True)
def edit_own_focus(n):
    return "own" if clicked(n) else no_update


@app.callback(Output("focus-edit", "data", allow_duplicate=True),
              Input("coach-cancel", "n_clicks"), prevent_initial_call=True)
def cancel_coach_focus(n):
    return None if clicked(n) else no_update


@app.callback(Output("focus-edit", "data", allow_duplicate=True),
              Input("own-cancel", "n_clicks"), prevent_initial_call=True)
def cancel_own_focus(n):
    return None if clicked(n) else no_update


@app.callback(Output("focus-history", "data"),
              Input("coach-history", "n_clicks"), State("focus-history", "data"),
              prevent_initial_call=True)
def show_coach_history(n, current):
    if not clicked(n):
        return no_update
    return None if current == "coach" else "coach"


@app.callback(Output("focus-history", "data", allow_duplicate=True),
              Input("own-history", "n_clicks"), State("focus-history", "data"),
              prevent_initial_call=True)
def show_own_history(n, current):
    if not clicked(n):
        return no_update
    return None if current == "own" else "own"


@app.callback(Output("f-setting", "data"), Output("recap", "data", allow_duplicate=True),
              Input({"type": "filter-setting", "s": ALL}, "n_clicks"),
              State("f-setting", "data"), prevent_initial_call=True)
def pick_setting_filter(clicks, current):
    if not any(c for c in clicks if c):
        return current, no_update
    # A recap describes a particular set of entries. Change the set and the
    # old recap is about something else, so it goes.
    return ctx.triggered_id["s"], None


@app.callback(Output("f-author", "data"), Output("recap", "data", allow_duplicate=True),
              Input("filter-author", "value"), prevent_initial_call=True)
def pick_author_filter(value):
    return value or "", None


@app.callback(Output("adding-player", "data"),
              Input("add-player-open", "n_clicks"), State("adding-player", "data"),
              prevent_initial_call=True)
def open_add_player(n, showing):
    return (not showing) if clicked(n) else no_update


def new_player(name: str, age) -> str:
    """Put a player on the roster and hand back their id.

    Both the roster form and the new-lesson shortcut come through here, so an
    id made one way is made the same way the other.
    """
    slug = "".join(ch for ch in name.lower().split()[0] if ch.isalpha()) or "player"
    pid, n_try = slug, 1
    while db.person(pid):
        n_try += 1
        pid = f"{slug}{n_try}"
    # Read everything the write needs *before* opening the transaction.
    # Calling anything that touches the database from inside one deadlocks.
    joined = clock.today_iso()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO people (id, name, role, age, joined_on) "
            "VALUES (?,?,'player',?,?)",
            (pid, name.strip(), int(age) if age else None, joined))
    return pid


@app.callback(Output("added-msg", "data"),
              Output("roster-changed", "data", allow_duplicate=True),
              Output("new-player-name", "value"),
              Output("new-player-age", "value"),
              Input("add-player", "n_clicks"),
              State("new-player-name", "value"), State("new-player-age", "value"),
              State("who", "value"), State("roster-changed", "data"),
              prevent_initial_call=True)
def add_player(n, name, age, who, tick):
    """A coach putting a new player into the system.

    Minimal on purpose — a name and an age. Everything else about a player
    accumulates from being coached, and asking for it up front is a form
    nobody fills in.
    """
    person = db.person(who)
    if not clicked(n) or person is None or person["role"] not in ("coach", "admin"):
        return no_update, no_update, no_update, no_update
    if not name or not name.strip():
        return "Needs a name.", no_update, no_update, no_update
    new_player(name, age)
    # The form stays open with the fields cleared, so you can see it worked
    # and add the next one. Closing it on success looked like nothing had
    # happened, because the confirmation closed with it.
    return f"Added {name.strip()}.", (tick or 0) + 1, "", None


@app.callback(Output("lesson-query", "data"),
              Input("lesson-search", "value"), prevent_initial_call=True)
def type_lesson_search(value):
    return value or ""


@app.callback(Output("sel-player", "data", allow_duplicate=True),
              Output("nav", "data", allow_duplicate=True),
              Output("draft", "data", allow_duplicate=True),
              Input({"type": "start-lesson", "id": ALL}, "n_clicks"),
              State("who", "value"), prevent_initial_call=True)
def start_lesson_with(clicks, who):
    """Pick a player off the roster and go straight to writing it up.

    Same destination as Write up a lesson on their page — this just saves
    the trip through Players to get there.
    """
    person = db.person(who)
    if person is None or person["role"] not in ("coach", "admin"):
        return no_update, no_update, no_update
    if not ctx.triggered_id or not any(c for c in clicks if c):
        return no_update, no_update, no_update
    pid = ctx.triggered_id["id"]
    return pid, "note", {"player_id": pid, "setting": "lesson",
                         "on": clock.today_iso(), "text": "", "organized": None}


@app.callback(Output("plan-edit", "data"),
              Input("edit-plan", "n_clicks"), prevent_initial_call=True)
def open_plan_editor(n):
    return True if clicked(n) else no_update


@app.callback(Output("plan-edit", "data", allow_duplicate=True),
              Input("cancel-plan", "n_clicks"), prevent_initial_call=True)
def close_plan_editor(n):
    return False if clicked(n) else no_update


@app.callback(Output("plan-edit", "data", allow_duplicate=True),
              Input("save-plan", "n_clicks"),
              State("plan-work", "value"), State("plan-targets", "value"),
              State("plan-keys", "value"), prevent_initial_call=True)
def save_plan(n, work, targets, keys):
    if not clicked(n):
        return no_update
    cv.save_week_plan(db.ensure_week(clock.today_iso()), work, targets, keys)
    return False


@app.callback(Output("sel-player", "data", allow_duplicate=True),
              Output("roster-changed", "data", allow_duplicate=True),
              Input("remove-player", "n_clicks"), State("sel-player", "data"),
              State("who", "value"), State("roster-changed", "data"),
              prevent_initial_call=True)
def drop_player(n, player_id, who, tick):
    person = db.person(who)
    if not clicked(n) or not player_id or person is None:
        return no_update, no_update
    if person["role"] != "admin":
        return no_update, no_update
    db.remove_player(player_id)
    return None, (tick or 0) + 1


@app.callback(Output("who", "options"), Input("roster-changed", "data"))
def refresh_people(_tick):
    return people_options()


@app.callback(Output("nav", "data", allow_duplicate=True),
              Input("open-recap", "n_clicks"), prevent_initial_call=True)
def go_to_recap(n):
    return "recap" if clicked(n) else no_update


@app.callback(
    Output("page", "children"),
    Input("who", "value"), Input("nav", "data"),
    Input("sel-player", "data"), Input("pb-sec", "data"),
    Input("today-label", "children"), Input("poll", "disabled"),
    Input("review", "data"), Input("answer", "data"),
    Input("theme-tick", "data"), Input("draft", "data"),
    Input("recap", "data"), Input("recap-range", "data"), Input("cal-offset", "data"),
    Input("sel-day", "data"), Input("day-summary", "data"),
    Input("lesson-arc", "data"), Input("focus-tick", "data"),
    Input("search", "data"), Input("year-sel", "data"),
    Input("open-month", "data"), Input("show-entries", "data"),
    Input("kind", "data"), Input("editing", "data"),
    Input("focus-edit", "data"), Input("focus-history", "data"),
    Input("f-setting", "data"), Input("f-author", "data"),
    Input("recap-year", "data"), Input("lesson-query", "data"),
    Input("adding-player", "data"), Input("added-msg", "data"),
    Input("plan-edit", "data"),
    State("job", "data"),
)
def render_page(who, nav, sel_player, pb_sec, _label, _polling,
                review, answer, theme_msg, draft, recap, recap_range,
                cal_offset, sel_day, day_summary, lesson_arc, focus_msg,
                search, year, open_month, show_entries, kind, editing,
                focus_edit, focus_hist, f_setting, f_author, recap_year, lesson_query, adding,
                added_msg, plan_edit, job_id):
    person = db.person(who)
    if person is None:
        return html.Div("Unknown person.", className="card")
    running = job(job_id)["state"] == "running"

    if nav == "usage":
        return usage_page()

    role = person["role"]

    if role == "player":
        if nav == "lessons":
            return cv.lesson_months(who, None, "player", open_month, year,
                                    sel_day, running, editing)
        if nav == "recap":
            return cv.recap_panel(who, "player", recap_range, recap, running,
                                  show_entries, f_setting, f_author, recap_year)
        return html.Div([
            *player_today(who),
            cv.focus_pair(who, "player", focus_msg, focus_edit, focus_hist),
            player_reflections(who, "shared", job_id, kind),
            cv.recap_summary(who, "player", recap_range, recap, running),
        ])

    if role == "parent":
        return cv.parent_page(who)

    if role in ("coach", "admin"):
        if nav == "resources":
            return cv.resources(answer, running, pb_sec or 1)
        if nav == "note":
            return cv.note_composer(draft, running)
        if nav == "lessons":
            if not sel_player:
                return cv.coach_lesson_picker(who, lesson_query)
            return cv.lesson_months(sel_player, who, "coach", open_month,
                                    year, sel_day, running, editing)
        if nav == "recap":
            if not sel_player:
                return cv.coach_lesson_picker(who, lesson_query)
            return cv.recap_panel(sel_player, "coach", recap_range, recap, running,
                                  show_entries, f_setting, f_author, recap_year)
        if nav == "players":
            if sel_player:
                return html.Div([
                    cv.player_detail(sel_player, review, running, focus_msg,
                                     focus_edit, focus_hist,
                                     person['role'] == 'admin'),
                    cv.recap_summary(sel_player, "coach", recap_range, recap,
                                     running),
                ])
            return cv.roster(search, adding, added_msg)
        return cv.coach_today(who, theme_msg, plan_edit)

    return html.Div("Nothing here.", className="card")


if __name__ == "__main__":
    db.init_db()
    if not db.people("player"):
        seed.build()
    if not key_is_set():
        print("!! PORTKEY_API_KEY not found — agent calls will fail.")
    print(f"\n  Rebound on http://127.0.0.1:8050   model={MODEL_NAME}")
    print(f"  simulated today: {clock.today()}\n")
    # debug off and the reloader disabled, so one edit does not spawn a second server
    app.run(debug=False, use_reloader=False, port=8050)
