"""Rebound — a shared training diary for a junior squash academy.

Run:  ./venv/bin/python app.py     then open http://127.0.0.1:8050

No login. The "I am…" switcher at the top changes who you are, because the
point of a demo is to see the same week from a coach's side and a kid's side
and a parent's side within about thirty seconds.

The agent call runs on a worker thread with a dcc.Interval polling for the
result, rather than inside the callback. A model call takes several seconds
and a Dash callback that blocks for that long freezes the whole page.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import date

from dash import Dash, Input, Output, State, ctx, dcc, html, no_update

from core import clock, db, metering
from core.agents import organizer
from core.config import MODEL_NAME, key_is_set
from data import seed

# ---------------------------------------------------------------- jobs

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def start_job(player_id: str, text: str, visibility: str) -> str:
    """Hand an entry to the Organizer on a worker thread."""
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {"state": "running"}

    def work() -> None:
        try:
            on = clock.today_iso()
            organized, usage = asyncio.run(
                organizer.organize_player_entry(player_id, text, on)
            )
            db.add_entry(
                player_id=player_id,
                author_id=player_id,
                author_role="player",
                setting=organized.setting,
                rung=organized.rung,
                shot=organized.shot,
                category=organized.category,
                cue_id=organized.cue_id,
                raw_text=text,
                summary=organized.summary,
                visibility=visibility,
                occurred_on=on,
                flagged_injection=organized.injected_instruction,
                flagged_welfare=organized.welfare_flag,
            )
            with _JOBS_LOCK:
                _JOBS[job_id] = {"state": "done", "usage": usage,
                                 "flagged": organized.injected_instruction,
                                 "welfare": organized.welfare_flag}
        except Exception as exc:  # noqa: BLE001 — surfaced to the user, not swallowed
            with _JOBS_LOCK:
                _JOBS[job_id] = {"state": "error", "message": str(exc)[:200]}

    threading.Thread(target=work, daemon=True).start()
    return job_id


def job_state(job_id: str | None) -> dict:
    if not job_id:
        return {"state": "idle"}
    with _JOBS_LOCK:
        return dict(_JOBS.get(job_id, {"state": "idle"}))


# ---------------------------------------------------------------- pieces

CATEGORY_ORDER = ("technical", "tactical", "physical", "psychological")


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


def today_card(player_id: str):
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
                f"Squad is on the {week['theme_shot']} this week. The blocked and routine "
                f"parts are where you get to think about your own focus — that is the "
                f"slowest the session gets.", className="tiein"))
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


def reflections_panel(player_id: str, tab: str, job_id: str | None):
    private = tab == "private"
    entries = [e for e in db.entries_for_player(player_id)
               if (e["visibility"] == "private") == private
               and (e["author_id"] == player_id or not private)]
    entries.reverse()

    cards = [c for c in (entry_card(e, "player") for e in entries) if c]
    body = cards or [html.Div(
        "Nothing here yet." if private else "No shared reflections yet.", className="empty")]

    job = job_state(job_id)
    status = []
    if job["state"] == "running":
        status = [html.Span(className="spinner"), html.Span("  Filing it…", className="hint")]
    elif job["state"] == "error":
        status = [html.Span(f"Could not save that: {job['message']}", className="hint")]

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
                dcc.Textarea(
                    id="composer",
                    placeholder="How did it go? Talk or type — a sentence is plenty."
                    if not private else "Anything you want to keep to yourself.",
                ),
                html.Div([
                    html.Button("🎤", id="mic", className="mic", title="Speak instead"),
                    html.Button("Save", id="save", className="primary"),
                    html.Span(status, id="save-status"),
                ], className="composer-row"),
            ], className="composer"),
            html.Hr(style={"border": "0", "borderTop": "1px solid var(--line)",
                           "margin": "18px 0"}),
            *body,
        ], className=f"card{' private-pane' if private else ''}"),
    ])


def usage_page():
    totals = metering.totals()
    rows = metering.ledger_rows()[-25:][::-1]

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
        banner = [html.Div(
            "Token counts are real and measured. Cost shows $0 until the per-million "
            "token rates are set — see REBOUND_PRICE_IN / _CACHED / _OUT.",
            className="banner")]

    table = html.Table([
        html.Thead(html.Tr([html.Th("When"), html.Th("Agent"),
                            html.Th("In", className="num"), html.Th("Cached", className="num"),
                            html.Th("Out", className="num"), html.Th("Secs", className="num")])),
        html.Tbody([
            html.Tr([
                html.Td(r["at"][:19].replace("T", " ")),
                html.Td(r["agent"]),
                html.Td(f"{r['input_tokens']:,}", className="num"),
                html.Td(f"{r['cached_input_tokens']:,}", className="num"),
                html.Td(f"{r['output_tokens']:,}", className="num"),
                html.Td(f"{r['seconds']:.1f}", className="num"),
            ]) for r in rows
        ]),
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


def placeholder(role: str):
    return html.Div([
        html.H2(f"{role} view"),
        html.Div("Coming in the next phase.", className="empty"),
    ], className="card")


# ---------------------------------------------------------------- app

app = Dash(__name__, title="Rebound — Squash Tigers")
server = app.server


def people_options():
    options = []
    for role, label in (("player", "Players"), ("coach", "Coaches"), ("parent", "Parents")):
        for person in db.people(role):
            suffix = f" (age {person['age']})" if person["age"] else ""
            options.append({"label": f"{label[:-1]}: {person['name']}{suffix}",
                            "value": person["id"]})
    return options


app.layout = html.Div([
    dcc.Store(id="tab", data="shared"),
    dcc.Store(id="job", data=None),
    dcc.Interval(id="poll", interval=400, disabled=True),

    html.Div([
        html.Div(["Re", html.Span("bound")], className="brand"),
        html.Label("I am"),
        dcc.Dropdown(id="who", options=people_options(), value="maya",
                     clearable=False, style={"width": "260px"}),
        html.Div([
            html.Button("‹", id="back-week", className="step", title="Back a week"),
            html.Div(id="today-label", className="today"),
            html.Button("›", id="fwd-week", className="step", title="Forward a week"),
            html.Button("⟲", id="reset-clock", className="step", title="Back to the start"),
        ], className="datebar"),
        html.Button("Usage", id="show-usage", className="step"),
    ], className="topbar"),

    html.Div(id="page", className="page"),
])


@app.callback(
    Output("today-label", "children"),
    Input("back-week", "n_clicks"), Input("fwd-week", "n_clicks"),
    Input("reset-clock", "n_clicks"),
)
def move_clock(_b, _f, _r):
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


@app.callback(
    Output("tab", "data"),
    Input("tab-shared", "n_clicks"), Input("tab-private", "n_clicks"),
    State("tab", "data"),
    prevent_initial_call=True,
)
def switch_tab(shared_clicks, private_clicks, current):
    # These buttons are rebuilt every time the page re-renders, and a freshly
    # mounted button fires this callback with n_clicks of None. Without the
    # truthiness check, saving an entry would silently throw you out of the
    # private tab — which, on this tab in particular, is not a cosmetic bug.
    if ctx.triggered_id == "tab-private" and private_clicks:
        return "private"
    if ctx.triggered_id == "tab-shared" and shared_clicks:
        return "shared"
    return current


@app.callback(
    Output("job", "data"), Output("poll", "disabled"), Output("composer", "value"),
    Input("save", "n_clicks"),
    State("composer", "value"), State("who", "value"), State("tab", "data"),
    prevent_initial_call=True,
)
def save_entry(_n, text, who, tab):
    person = db.person(who)
    if not text or not text.strip() or not person or person["role"] != "player":
        return no_update, no_update, no_update
    job_id = start_job(who, text.strip(), "private" if tab == "private" else "shared")
    return job_id, False, ""


@app.callback(
    Output("poll", "disabled", allow_duplicate=True),
    Input("poll", "n_intervals"), State("job", "data"),
    prevent_initial_call=True,
)
def stop_polling(_n, job_id):
    return job_state(job_id)["state"] != "running"


@app.callback(
    Output("page", "children"),
    Input("who", "value"), Input("tab", "data"), Input("today-label", "children"),
    Input("poll", "disabled"), Input("show-usage", "n_clicks"),
    State("job", "data"),
)
def render_page(who, tab, _label, _polling, usage_clicks, job_id):
    if ctx.triggered_id == "show-usage" and usage_clicks:
        return usage_page()
    person = db.person(who)
    if person is None:
        return html.Div("Unknown person.", className="card")
    if person["role"] == "player":
        return html.Div([*today_card(who), reflections_panel(who, tab, job_id)])
    return placeholder(person["role"].title())


if __name__ == "__main__":
    db.init_db()
    if not db.people("player"):
        seed.build()
    if not key_is_set():
        print("!! PORTKEY_API_KEY not found — saving an entry will fail.")
    print(f"\n  Rebound on http://127.0.0.1:8050   model={MODEL_NAME}")
    print(f"  simulated today: {clock.today()}\n")
    # debug off and the reloader disabled, so one edit does not spawn a second server
    app.run(debug=False, use_reloader=False, port=8050)
