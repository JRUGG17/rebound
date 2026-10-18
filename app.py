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

import asyncio
import threading
import uuid

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

import coach_views as cv
from core import analysis, clock, db, metering
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


def job(job_id: str | None) -> dict:
    if not job_id:
        return {"state": "idle"}
    with _JOBS_LOCK:
        return dict(_JOBS.get(job_id, {"state": "idle"}))


def save_reflection(player_id: str, text: str, visibility: str):
    def work():
        on = clock.today_iso()
        organized, _usage = asyncio.run(
            organizer.organize_player_entry(player_id, text, on))
        db.add_entry(
            player_id=player_id, author_id=player_id, author_role="player",
            setting=organized.setting, rung=organized.rung, shot=organized.shot,
            category=organized.category, cue_id=organized.cue_id,
            raw_text=text, summary=organized.summary, visibility=visibility,
            occurred_on=on,
            flagged_injection=organized.injected_instruction,
            flagged_welfare=organized.welfare_flag,
        )
        return {"ok": True}
    return _run_job(work)


def file_coach_note(player_id: str, text: str, setting: str):
    def work():
        organized, _usage = asyncio.run(
            organizer.organize_coach_note(player_id, text, clock.today_iso()))
        return {"coach_note": organized.model_dump()}
    return _run_job(work)


def run_comparison(player_id: str):
    def work():
        review, _usage = asyncio.run(comparison.review_player(player_id))
        return review.model_dump()
    return _run_job(work)


def run_recap(player_id: str, start: str, end: str, audience: str):
    def work():
        output, _usage = asyncio.run(
            recap_agent.recap_period(player_id, start, end, audience=audience))
        return {"recap": output.model_dump() if output else None}
    return _run_job(work)


def ask_playbook(question: str):
    def work():
        answer, _usage = asyncio.run(methodology.ask(question))
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
    player = db.person(player_id)
    focus = db.current_focus(player_id)
    week = db.week_of(clock.today_iso())
    cards = []

    if focus:
        cards.append(html.Div([
            html.H2("Your focus right now"),
            html.Div(focus["text"], className="focus-text"),
            html.Div(f"Set by {db.person(focus['coach_id'])['name']} on {focus['set_on']}",
                     className="byline"),
        ], className="card focus-card"))

    if week:
        tie = []
        if focus and week["theme_shot"]:
            tie.append(html.Div(
                f"Squad is on the {week['theme_shot']} this week. The blocked and "
                f"routine parts are where you get to think about your own focus — "
                f"that is the slowest the session gets.", className="tiein"))
        cards.append(html.Div([
            html.H2("This week at squad"),
            html.Div(html.Span(week["theme_name"], className="theme-pill")),
            *tie,
        ], className="card"))

    cards.append(html.Div([
        html.H2("Nudge"),
        html.Div(f"{player['name'].split()[0]}, you have not logged anything since the "
                 f"last squad. Thirty seconds is plenty — just say how it went.",
                 className="tiein"),
    ], className="card"))
    return cards


def player_reflections(player_id: str, tab: str, job_id: str | None):
    private = tab == "private"
    entries = [e for e in db.entries_for_player(player_id)
               if (e["visibility"] == "private") == private
               and (e["author_id"] == player_id or not private)]
    entries.reverse()

    cards = [c for c in (entry_card(e, "player") for e in entries) if c]
    body = cards or [html.Div(
        "Nothing here yet." if private else "No shared reflections yet.", className="empty")]

    state = job(job_id)
    status = []
    if state["state"] == "running":
        status = [html.Span(className="spinner"), html.Span("  Filing it…", className="hint")]
    elif state["state"] == "error":
        status = [html.Span(f"Could not save that: {state['message']}", className="hint")]

    note = []
    if private:
        note = [html.Div(
            "🔒 Only you can read this tab. Your coaches cannot see it and are not told "
            "it exists. If you write something that makes us worried about you, a "
            "designated adult and your parent will be told — and so will you.",
            className="private-note")]

    return html.Div([
        html.Div([
            html.Button("Shared with my coaches", id="tab-shared",
                        className=f"tab-btn{'' if private else ' active'}"),
            html.Button("🔒 Just me", id="tab-private",
                        className=f"tab-btn private{' active' if private else ''}"),
        ], className="tab-row"),
        html.Div([
            *note,
            html.Div([
                dcc.Textarea(id="composer",
                             placeholder="How did it go? Talk or type — a sentence is "
                             "plenty." if not private
                             else "Anything you want to keep to yourself."),
                html.Div([
                    html.Button("🎤", id="mic", className="mic", title="Speak instead"),
                    html.Button("Save", id="save", className="primary"),
                    html.Span(status),
                ], className="composer-row"),
            ], className="composer"),
            html.Hr(style={"border": 0, "borderTop": "1px solid var(--line)",
                           "margin": "18px 0"}),
            *body,
        ], className=f"card{' private-pane' if private else ''}"),
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
         "prices not set" if not metering.PRICES_CONFIGURED else "measured"),
    ]
    banner = []
    if not metering.PRICES_CONFIGURED:
        banner = [html.Div("Token counts are real and measured. Cost shows $0 until the "
                           "per-million token rates are set.", className="banner")]
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
    dcc.Store(id="tab", data="shared"),
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
    dcc.Store(id="recap-range", data="block"),
    dcc.Store(id="recap", data=None),
    dcc.Store(id="cal-offset", data=0),
    dcc.Interval(id="poll", interval=400, disabled=True),

    html.Div([
        html.Div(["Re", html.Span("bound")], className="brand"),
        html.Label("I am"),
        dcc.Dropdown(id="who", options=people_options(), value="maya",
                     clearable=False, style={"width": "250px"}),
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
)
def move_clock(_b, _f, _r, _nav):
    if ctx.triggered_id == "back-week":
        clock.shift(-7)
    elif ctx.triggered_id == "fwd-week":
        clock.shift(7)
    elif ctx.triggered_id == "reset-clock":
        clock.reset()
    today = clock.today()
    week = db.week_of(today.isoformat())
    label = today.strftime("%a %d %b %Y")
    return f"{label} · {week['theme_name']}" if week else label


PLAYER_NAV = [
    (None, [("today", "Today")]),
    ("Journal", [("calendar", "Calendar"), ("recap", "Recap")]),
    (None, [("usage", "Usage")]),
]
COACH_NAV = [
    (None, [("today", "Today"), ("players", "Players"), ("note", "Add note")]),
    ("Journal", [("calendar", "Calendar"), ("recap", "Recap")]),
    (None, [("resources", "Coach resources"), ("usage", "Usage")]),
]


@app.callback(Output("sidebar", "children"), Input("who", "value"), Input("nav", "data"),
              Input("sel-player", "data"))
def render_sidebar(who, nav, sel_player):
    person = db.person(who)
    if person is None:
        return None
    groups = COACH_NAV if person["role"] in ("coach", "admin") else PLAYER_NAV

    out = []
    for heading, items in groups:
        if heading:
            out.append(html.Div(heading, className="side-heading"))
        for key, label in items:
            out.append(html.Button(label, id={"type": "nav", "key": key},
                                   className=f"side-btn{' active' if nav == key else ''}"))
    # Whose journal a coach is reading has to be visible, or the Calendar and
    # Recap tabs silently mean a different player than the one they picked.
    if person["role"] in ("coach", "admin") and nav in ("calendar", "recap"):
        subject = db.person(sel_player) if sel_player else None
        out.append(html.Div(
            f"Showing {subject['name']}" if subject
            else "Pick a player under Players first", className="side-note"))
    return html.Div(out)


@app.callback(Output("nav", "data"), Output("sel-player", "data", allow_duplicate=True),
              Input({"type": "nav", "key": ALL}, "n_clicks"),
              State("nav", "data"), prevent_initial_call=True)
def switch_nav(clicks, current):
    if not ctx.triggered_id or not any(c for c in clicks if c):
        return current, no_update
    return ctx.triggered_id["key"], None


@app.callback(Output("nav", "data", allow_duplicate=True),
              Input("who", "value"), prevent_initial_call=True)
def reset_nav(_who):
    return "today"


@app.callback(
    Output("tab", "data"),
    Input("tab-shared", "n_clicks"), Input("tab-private", "n_clicks"),
    State("tab", "data"), prevent_initial_call=True,
)
def switch_tab(shared_clicks, private_clicks, current):
    # These buttons are rebuilt on every render, and a freshly mounted button
    # fires with n_clicks of None. Without the truthiness check, saving would
    # throw the user out of the private tab — not a cosmetic bug on that tab.
    if ctx.triggered_id == "tab-private" and private_clicks:
        return "private"
    if ctx.triggered_id == "tab-shared" and shared_clicks:
        return "shared"
    return current


# One callback per button, never several buttons in one. A Dash callback is
# dead while any of its Inputs is missing from the layout, and these buttons
# live on different screens — bundling them meant that saving a reflection
# stopped working whenever the coach's screens were not rendered.

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
    week = db.week_of(clock.today_iso())
    if not week:
        return "No week for this date."
    names = {"reset": "Reset Week", "attacking": "Attacking Week",
             "positional": "Positional Driving Week"}
    name = names.get(shot, f"{shot.title()} Week")
    with db.connect() as conn:
        conn.execute("UPDATE weeks SET theme_shot = ?, theme_name = ? WHERE id = ?",
                     (None if shot in names else shot, name, week["id"]))
    return f"Set to {name}."


# --------------------------------------------------- the one async channel

@app.callback(
    Output("job", "data"), Output("poll", "disabled"), Output("composer", "value"),
    Input("save", "n_clicks"),
    State("composer", "value"), State("who", "value"), State("tab", "data"),
    prevent_initial_call=True,
)
def start_save(n, text, who, tab):
    person = db.person(who)
    if not n or not text or not text.strip() or not person or person["role"] != "player":
        return no_update, no_update, no_update
    visibility = "private" if tab == "private" else "shared"
    return save_reflection(who, text.strip(), visibility), False, ""


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
    Input("poll", "n_intervals"), State("job", "data"), State("draft", "data"),
    prevent_initial_call=True,
)
def collect(_n, job_id, draft):
    state = job(job_id)
    if state["state"] == "running":
        return False, no_update, no_update, no_update, no_update
    result = state.get("result")
    if state["state"] == "done" and isinstance(result, dict):
        if "findings" in result:
            return True, result, no_update, no_update, no_update
        if "answer" in result:
            return True, no_update, result, no_update, no_update
        if "coach_note" in result and draft:
            return True, no_update, no_update, {**draft, "organized": result["coach_note"]}, no_update
        if "recap" in result:
            return True, no_update, no_update, no_update, result["recap"]
    return True, no_update, no_update, no_update, no_update


# --------------------------------------------------- writing a lesson note

@app.callback(
    Output("job", "data", allow_duplicate=True),
    Output("poll", "disabled", allow_duplicate=True),
    Output("draft", "data", allow_duplicate=True),
    Input("file-note", "n_clicks"),
    State("note-player", "value"), State("note-text", "value"),
    State("note-setting", "value"),
    prevent_initial_call=True,
)
def start_file_note(n, player_id, text, setting):
    if not n or not player_id or not text or not text.strip():
        return no_update, no_update, no_update
    draft = {"player_id": player_id, "text": text.strip(),
             "setting": setting or "lesson", "organized": None}
    return file_coach_note(player_id, text.strip(), setting or "lesson"), False, draft


@app.callback(
    Output("draft", "data", allow_duplicate=True),
    Input("release-note", "n_clicks"), Input("keep-note", "n_clicks"),
    State("draft", "data"), State("note-player-text", "value"), State("who", "value"),
    prevent_initial_call=True,
)
def save_note(_release, _keep, draft, player_text, coach_id):
    if not draft or not draft.get("organized"):
        return no_update
    release = ctx.triggered_id == "release-note"
    organized = draft["organized"]
    db.add_entry(
        player_id=draft["player_id"], author_id=coach_id, author_role="coach",
        setting=draft["setting"], rung=organized.get("rung"),
        shot=organized.get("shot"), category=organized.get("category"),
        cue_id=organized.get("cue_id"), raw_text=draft["text"],
        summary=organized.get("summary"),
        player_text=(player_text or "").strip() or None,
        # Releasing is the approval. A note kept back stays a coach record and
        # the player is shown nothing, rather than the coach's raw words.
        approved_by=coach_id if release else None,
        visibility="shared",
        occurred_on=clock.today_iso(),
    )
    name = db.person(draft["player_id"])["name"].split()[0]
    return {"saved": f"Saved{' and released to ' + name if release else ' as coach-only'}."}


@app.callback(Output("cal-offset", "data"),
              Input("cal-prev", "n_clicks"), Input("cal-next", "n_clicks"),
              State("cal-offset", "data"), prevent_initial_call=True)
def move_calendar(prev_clicks, next_clicks, offset):
    offset = offset or 0
    if ctx.triggered_id == "cal-prev" and prev_clicks:
        return offset - 1
    if ctx.triggered_id == "cal-next" and next_clicks:
        return offset + 1
    return offset


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
    prevent_initial_call=True,
)
def start_recap(n, who, sel_player, range_key):
    person = db.person(who)
    if not n or person is None:
        return no_update, no_update
    is_player = person["role"] == "player"
    subject = who if is_player else sel_player
    if not subject:
        return no_update, no_update
    start, end, _label = cv.range_bounds(range_key or "block")
    return run_recap(subject, start, end, "player" if is_player else "coach"), False


@app.callback(
    Output("page", "children"),
    Input("who", "value"), Input("nav", "data"), Input("tab", "data"),
    Input("sel-player", "data"), Input("pb-sec", "data"),
    Input("today-label", "children"), Input("poll", "disabled"),
    Input("review", "data"), Input("answer", "data"),
    Input("theme-tick", "data"), Input("draft", "data"),
    Input("recap", "data"), Input("recap-range", "data"), Input("cal-offset", "data"),
    State("job", "data"),
)
def render_page(who, nav, tab, sel_player, pb_sec, _label, _polling,
                review, answer, theme_msg, draft, recap, recap_range,
                cal_offset, job_id):
    person = db.person(who)
    if person is None:
        return html.Div("Unknown person.", className="card")
    running = job(job_id)["state"] == "running"

    if nav == "usage":
        return usage_page()

    role = person["role"]
    if role == "player":
        if nav == "calendar":
            return cv.calendar_view(who, "player", cal_offset or 0)
        if nav == "recap":
            return cv.recap_view(who, "player", recap_range, recap, running)
        return html.Div([*player_today(who), player_reflections(who, tab, job_id)])
    if role == "parent":
        return cv.parent_page(who)
    if role in ("coach", "admin"):
        if nav == "calendar":
            if not sel_player:
                return html.Div("Open a player under Players first.", className="card")
            return cv.calendar_view(sel_player, "coach", cal_offset or 0)
        if nav == "recap":
            if not sel_player:
                return html.Div("Open a player under Players first.", className="card")
            return cv.recap_view(sel_player, "coach", recap_range, recap, running)
        if nav == "note":
            return cv.note_composer(draft, running)
        if nav == "resources":
            return cv.resources(answer, running, pb_sec or 1)
        if nav == "players":
            if sel_player:
                return cv.player_detail(sel_player, review, running)
            return cv.roster()
        return cv.coach_today(who, theme_msg)
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
