"""SQLite layer.

One table does most of the work: `entries`. Everything anyone says about a
player — a kid's reflection, a coach's lesson note, a tournament result — is an
entry, tagged with where it came from and which rung of the ladder it was on.

**The visibility boundary lives here, not in a prompt.** A player's private
entry must never reach a coach-facing agent, so there is no function on this
module that returns every entry for a player. Coach-side callers go through
`entries_for_coach()`, which filters in SQL. A prompt can be talked out of a
rule; a WHERE clause cannot.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Literal

from core.config import REPO_ROOT

DB_PATH = Path(os.getenv("REBOUND_DB", REPO_ROOT / "data" / "rebound.db"))

Role = Literal["player", "coach", "parent"]
Setting = Literal["lesson", "squad", "solo", "tournament", "reflection"]
Rung = Literal["solo", "block", "routine", "pattern", "conditioned_game", "match"]
Category = Literal["technical", "tactical", "physical", "psychological"]
Visibility = Literal["shared", "private"]

# The ladder, in order. Index into this to compare rungs.
RUNGS: tuple[str, ...] = ("solo", "block", "routine", "pattern", "conditioned_game", "match")
SHOTS: tuple[str, ...] = ("drive", "boast", "drop", "lob")

SCHEMA = """
-- role is validated in Python, not by a CHECK. A CHECK constraint cannot be
-- altered in SQLite without rebuilding the table, and roles are exactly the
-- sort of thing that gains a member later — 'admin' did.
CREATE TABLE IF NOT EXISTS people (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,
    age         INTEGER,
    child_id    TEXT REFERENCES people(id),   -- parents only
    joined_on   TEXT
);

-- The curriculum calendar. One row per week, four-week rotation.
CREATE TABLE IF NOT EXISTS weeks (
    id          INTEGER PRIMARY KEY,
    starts_on   TEXT NOT NULL UNIQUE,
    theme_shot  TEXT,                          -- drive | boast | drop | lob, or NULL
    theme_name  TEXT NOT NULL,                 -- "Drop Week", "Reset Week"
    block_no    INTEGER NOT NULL,              -- twelve-week block
    cycle_no    INTEGER NOT NULL               -- which pass through the four shots
);

-- A player's current technical focus, set in a private lesson.
CREATE TABLE IF NOT EXISTS focuses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id    TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    coach_id     TEXT NOT NULL REFERENCES people(id),
    text         TEXT NOT NULL,
    category     TEXT NOT NULL,
    cue_id       TEXT,
    set_on       TEXT NOT NULL,
    resolved_on  TEXT
);
CREATE INDEX IF NOT EXISTS idx_focus_player ON focuses(player_id, set_on);

CREATE TABLE IF NOT EXISTS entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id     TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    author_id     TEXT NOT NULL REFERENCES people(id),
    author_role   TEXT NOT NULL,
    setting       TEXT NOT NULL,
    rung          TEXT,
    shot          TEXT,
    category      TEXT,
    cue_id        TEXT,
    proposed_cue  TEXT,
    raw_text      TEXT NOT NULL,               -- what was actually said
    summary       TEXT,                        -- what the Organizer made of it
    player_text   TEXT,                        -- a coach note rewritten for the kid
    player_text_approved_by  TEXT,              -- the coach who signed that rewrite off
    player_text_approved_at  TEXT,              -- when; NULL means not yet released
    visibility    TEXT NOT NULL DEFAULT 'shared'
                  CHECK (visibility IN ('shared', 'private')),
    media_url     TEXT,                        -- optional clip link, never uploaded
    occurred_on   TEXT NOT NULL,               -- simulated date
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entry_player ON entries(player_id, occurred_on);
CREATE INDEX IF NOT EXISTS idx_entry_vis ON entries(player_id, visibility);

-- Canonical cue library, loaded from the playbook.
CREATE TABLE IF NOT EXISTS cues (
    id         TEXT PRIMARY KEY,
    canonical  TEXT NOT NULL,
    category   TEXT NOT NULL
);

-- Generated summaries, kept so a stretch of time is paid for once.
CREATE TABLE IF NOT EXISTS summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id    TEXT NOT NULL,
    kind         TEXT NOT NULL,        -- recap | day | lessons
    audience     TEXT NOT NULL,
    span_start   TEXT NOT NULL,
    span_end     TEXT NOT NULL,
    payload      TEXT NOT NULL,        -- the agent's output as JSON
    entry_count  INTEGER NOT NULL,     -- what it was built from
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL,
    UNIQUE (player_id, kind, audience, span_start, span_end)
);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""


def _open() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """A transaction. Everything inside commits together or not at all.

    Do not run `executescript` in here — it commits implicitly, which ends the
    transaction underneath us. Use `init_db()`, which opens its own connection.
    """
    conn = _open()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Idempotent. Safe to call on every startup."""
    conn = _open()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
    finally:
        conn.close()


# Columns added after the first release. CREATE TABLE IF NOT EXISTS will not add
# a column to a table that already exists, so widen it here instead of making
# anyone delete their database.
_ADDED_COLUMNS = {
    "entries": [
        ("player_text", "TEXT"),
        # A rewrite reaches a child only once the coach who wrote the note has
        # read it and signed it off. Unapproved, the note stays a coach record.
        ("player_text_approved_by", "TEXT"),
        ("player_text_approved_at", "TEXT"),
        # Set by the Organizer when it files an entry. flagged_injection marks
        # text that tried to instruct an agent rather than record training.
        ("flagged_injection", "INTEGER NOT NULL DEFAULT 0"),
        ("flagged_welfare", "INTEGER NOT NULL DEFAULT 0"),
        # A coaching theme the Organizer saw recurring that no canonical cue
        # covers. Waiting on an admin to adopt it, or not.
        ("proposed_cue", "TEXT"),
    ],
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in _ADDED_COLUMNS.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    # The original people table had CHECK (role IN ('player','coach','parent')),
    # which 'admin' now violates. SQLite cannot drop a CHECK, so rebuild once.
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='people'"
    ).fetchone()
    if sql and "CHECK" in (sql["sql"] or ""):
        conn.executescript("""
            ALTER TABLE people RENAME TO people_old;
            CREATE TABLE people (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                age INTEGER, child_id TEXT REFERENCES people(id), joined_on TEXT
            );
            INSERT INTO people SELECT id, name, role, age, child_id, joined_on
              FROM people_old;
            DROP TABLE people_old;
        """)


# ---------------------------------------------------------------- settings

def get_setting(key: str, default: str = "") -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ---------------------------------------------------------------- people

def people(role: Role | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM people"
    args: tuple = ()
    if role:
        sql += " WHERE role = ?"
        args = (role,)
    with connect() as conn:
        return conn.execute(sql + " ORDER BY name", args).fetchall()


def person(person_id: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()


# ---------------------------------------------------------------- entries

def add_entry(
    *,
    player_id: str,
    author_id: str,
    author_role: str,
    setting: str,
    raw_text: str,
    occurred_on: str,
    rung: str | None = None,
    shot: str | None = None,
    category: str | None = None,
    cue_id: str | None = None,
    proposed_cue: str | None = None,
    summary: str | None = None,
    player_text: str | None = None,
    approved_by: str | None = None,
    visibility: str = "shared",
    media_url: str | None = None,
    flagged_injection: bool = False,
    flagged_welfare: bool = False,
) -> int:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO entries (player_id, author_id, author_role, setting, rung,
                   shot, category, cue_id, proposed_cue, raw_text, summary,
                   player_text, player_text_approved_by, player_text_approved_at,
                   visibility, media_url, occurred_on, created_at, flagged_injection,
                   flagged_welfare)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (player_id, author_id, author_role, setting, rung, shot, category, cue_id,
             proposed_cue, raw_text, summary, player_text, approved_by,
             now if approved_by else None, visibility, media_url, occurred_on, now,
             int(flagged_injection), int(flagged_welfare)),
        )
        return int(cursor.lastrowid or 0)


def agent_text(entry) -> str:
    """What a downstream agent is allowed to read for an entry.

    The Organizer is the airlock. It is the only agent that ever sees a
    player's raw words, and its job includes neutralising anything in them
    that was aimed at a model rather than at the record. Every agent after it
    reads the summary it produced, not the original string.

    That matters because the dangerous attack is not the one caught at the
    door — it is the one that sits in the database and gets read next week by
    a different agent building a coach's brief. A summary cannot carry an
    instruction the Organizer already stripped.

    Coach-authored notes pass through as written: they are staff records, and
    paraphrasing a coach to another coach loses the detail the brief is for.
    """
    if entry["author_role"] == "coach":
        return entry["raw_text"]
    if entry["flagged_injection"]:
        return (entry["summary"] or "[entry withheld]") + \
               "  [flagged: this entry contained text addressed at an agent]"
    return entry["summary"] or entry["raw_text"]


def render_for(entry, viewer_role: str) -> str | None:
    """The text an audience should be shown, or None if it is not for them.

    Everyone reads the same words — the ones whoever wrote the entry actually
    wrote. There used to be a second, kid-facing rendering of every coach
    note, generated by a model; it is gone, because a paraphrase changes
    meaning in ways the coach never sees.

    What is still true is that a coach note reaches the player only once that
    coach has released it. A note they keep back stays a coach record and the
    player is shown nothing, which is the honest way to write something not
    meant for a child.
    """
    if viewer_role == "coach":
        return entry["raw_text"]
    if entry["author_role"] != "coach":
        return entry["raw_text"]
    if not entry["player_text_approved_at"]:
        return None
    return entry["raw_text"]


def approve_player_text(entry_id: int, coach_id: str, *, edited: str | None = None) -> None:
    """Release a note to the player.

    `edited` lets a coach change their own wording on the way out — their
    edit replaces the note, rather than sitting beside it as a second
    version.
    """
    from datetime import datetime, timezone

    with connect() as conn:
        if edited is not None:
            conn.execute("UPDATE entries SET raw_text = ? WHERE id = ?",
                         (edited, entry_id))
        conn.execute(
            """UPDATE entries
               SET player_text_approved_by = ?, player_text_approved_at = ?
               WHERE id = ?""",
            (coach_id, datetime.now(timezone.utc).isoformat(), entry_id),
        )


def pending_approval(coach_id: str) -> list[sqlite3.Row]:
    """A coach's own notes whose kid-facing version is still unreleased."""
    with connect() as conn:
        return conn.execute(
            """SELECT * FROM entries
               WHERE author_id = ? AND author_role = 'coach'
                 AND visibility = 'shared' AND player_text_approved_at IS NULL
               ORDER BY occurred_on DESC""",
            (coach_id,),
        ).fetchall()


# "private" means different things depending on who wrote it:
#
#   a player's private entry   -> that player alone, never any coach or parent
#   a coach's private note     -> all coaches, never the player or parent
#
# so each audience gets its own query, and none of them is a filtered version
# of a function that could return everything.

def _rows(sql: str, args: list, since: str | None) -> list[sqlite3.Row]:
    if since:
        sql += " AND occurred_on >= ?"
        args = [*args, since]
    with connect() as conn:
        return conn.execute(sql + " ORDER BY occurred_on, id", args).fetchall()


def entries_for_coach(player_id: str, *, since: str | None = None) -> list[sqlite3.Row]:
    """What a coach — or any coach-facing agent — may see about a player.

    Coaches see each other's notes, shared or not. They never see a player's
    private entry, and never learn that one exists. That exclusion is a WHERE
    clause, not an instruction in a prompt: an injected string can talk a model
    out of a rule, but it cannot talk SQL into returning a row it filtered.
    """
    return _rows(
        """SELECT * FROM entries
           WHERE player_id = ?
             AND NOT (author_role = 'player' AND visibility = 'private')""",
        [player_id], since,
    )


def entries_for_player(player_id: str, *, since: str | None = None) -> list[sqlite3.Row]:
    """Their own entries, private included, plus coaches' released notes.

    A coach note reaches the child only once its kid-facing rewrite has been
    approved. Until then it is a coach record and nothing else — so a model's
    paraphrase can never be the first version of a note a child reads.
    """
    return _rows(
        """SELECT * FROM entries
           WHERE player_id = ?
             AND (author_id = ?
                  OR (author_role = 'coach'
                      AND visibility = 'shared'
                      AND player_text_approved_at IS NOT NULL))""",
        [player_id, player_id], since,
    )


def entries_for_parent(player_id: str, *, since: str | None = None) -> list[sqlite3.Row]:
    """Exactly what the child sees, minus the child's own private entries.

    A guardian observing adult-to-child contact should see what was actually
    said to their child, not a different version of it.
    """
    return _rows(
        """SELECT * FROM entries
           WHERE player_id = ?
             AND visibility = 'shared'
             AND (author_role = 'player' OR player_text_approved_at IS NOT NULL)""",
        [player_id], since,
    )


def visible_to(viewer_id: str, player_id: str, *, since: str | None = None) -> list[sqlite3.Row]:
    """Dispatch on the viewer's role. The UI calls this; agents call the
    specific function for their side, so the boundary is explicit at the call site.
    """
    viewer = person(viewer_id)
    if viewer is None:
        return []
    if viewer["role"] == "player":
        return entries_for_player(player_id, since=since) if viewer_id == player_id else []
    if viewer["role"] == "parent":
        return entries_for_parent(player_id, since=since) if viewer["child_id"] == player_id else []
    return entries_for_coach(player_id, since=since)


# ---------------------------------------------------------------- focus & weeks

def current_focus(player_id: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            """SELECT * FROM focuses WHERE player_id = ? AND resolved_on IS NULL
               ORDER BY set_on DESC LIMIT 1""",
            (player_id,),
        ).fetchone()


def week_of(date_iso: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM weeks WHERE starts_on <= ? ORDER BY starts_on DESC LIMIT 1",
            (date_iso,),
        ).fetchone()


# ---------------------------------------------------------------- cue proposals

def cue_proposals() -> list[dict]:
    """Themes the Organizer saw recurring that no canonical cue covers.

    Grouped by the exact phrasing proposed, most frequent first. Near-misses
    are not merged — "racket up early" and "early racket" stay separate — and
    that is deliberate: a human reads these, and quietly collapsing two of
    them would be the system deciding the academy's vocabulary for it.
    """
    with connect() as conn:
        rows = conn.execute(
            """SELECT proposed_cue AS phrase, COUNT(*) AS n,
                      COUNT(DISTINCT player_id) AS players,
                      MIN(occurred_on) AS first_on, MAX(occurred_on) AS last_on
               FROM entries
               WHERE proposed_cue IS NOT NULL AND proposed_cue != ''
                 AND cue_id IS NULL
               GROUP BY lower(trim(proposed_cue))
               ORDER BY n DESC, phrase"""
        ).fetchall()
    return [dict(r) for r in rows]


def adopt_cue(phrase: str, category: str) -> str:
    """Promote a proposal to a canonical cue, and tag the entries that raised it."""
    cue_id = "_".join(phrase.lower().split())[:40] or "cue"
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO cues (id, canonical, category) VALUES (?,?,?)",
            (cue_id, phrase.strip(), category))
        conn.execute(
            """UPDATE entries SET cue_id = ?
               WHERE cue_id IS NULL AND lower(trim(proposed_cue)) = lower(trim(?))""",
            (cue_id, phrase))
    return cue_id


# ---------------------------------------------------------------- summaries

def get_summary(player_id: str, kind: str, audience: str,
                start: str, end: str, entry_count: int) -> dict | None:
    """A summary already written for this exact stretch, if it is still true.

    Re-reading an unchanged month costs the same as reading it the first
    time, and gives the same answer, so it is paid for once. The entry count
    is part of the test: if something has been added to the period since, the
    stored summary no longer describes it and is ignored rather than served
    stale.
    """
    import json

    with connect() as conn:
        row = conn.execute(
            """SELECT * FROM summaries
               WHERE player_id = ? AND kind = ? AND audience = ?
                 AND span_start = ? AND span_end = ?""",
            (player_id, kind, audience, start, end),
        ).fetchone()
    if row is None or row["entry_count"] != entry_count:
        return None
    try:
        payload = json.loads(row["payload"])
    except json.JSONDecodeError:
        return None
    return {"payload": payload, "created_at": row["created_at"],
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"], "cached": True}


def put_summary(player_id: str, kind: str, audience: str, start: str, end: str,
                payload: dict, entry_count: int, usage=None) -> None:
    import json
    from datetime import datetime, timezone

    with connect() as conn:
        conn.execute(
            """INSERT INTO summaries (player_id, kind, audience, span_start, span_end,
                   payload, entry_count, input_tokens, output_tokens, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (player_id, kind, audience, span_start, span_end)
               DO UPDATE SET payload = excluded.payload,
                             entry_count = excluded.entry_count,
                             input_tokens = excluded.input_tokens,
                             output_tokens = excluded.output_tokens,
                             created_at = excluded.created_at""",
            (player_id, kind, audience, start, end, json.dumps(payload), entry_count,
             getattr(usage, "input_tokens", 0) or 0,
             getattr(usage, "output_tokens", 0) or 0,
             datetime.now(timezone.utc).isoformat()),
        )


def drop_summary(player_id: str, kind: str, audience: str,
                 start: str, end: str) -> None:
    with connect() as conn:
        conn.execute(
            """DELETE FROM summaries
               WHERE player_id = ? AND kind = ? AND audience = ?
                 AND span_start = ? AND span_end = ?""",
            (player_id, kind, audience, start, end))


def summary_savings() -> dict:
    """What the cache has been worth, for the Usage page."""
    with connect() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS stored,
                      COALESCE(SUM(input_tokens), 0) AS input_tokens,
                      COALESCE(SUM(output_tokens), 0) AS output_tokens
               FROM summaries"""
        ).fetchone()
    return dict(row)
