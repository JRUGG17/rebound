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
CREATE TABLE IF NOT EXISTS people (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('player', 'coach', 'parent')),
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
    raw_text      TEXT NOT NULL,               -- what was actually said
    summary       TEXT,                        -- what the Organizer made of it
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
    finally:
        conn.close()


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
    summary: str | None = None,
    visibility: str = "shared",
    media_url: str | None = None,
) -> int:
    from datetime import datetime, timezone

    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO entries (player_id, author_id, author_role, setting, rung,
                   shot, category, cue_id, raw_text, summary, visibility, media_url,
                   occurred_on, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (player_id, author_id, author_role, setting, rung, shot, category, cue_id,
             raw_text, summary, visibility, media_url, occurred_on,
             datetime.now(timezone.utc).isoformat()),
        )
        return int(cursor.lastrowid or 0)


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
    """Their own entries, private included, plus coaches' shared notes."""
    return _rows(
        """SELECT * FROM entries
           WHERE player_id = ?
             AND (author_id = ? OR (author_role = 'coach' AND visibility = 'shared'))""",
        [player_id, player_id], since,
    )


def entries_for_parent(player_id: str, *, since: str | None = None) -> list[sqlite3.Row]:
    """Read-only, and only what everybody can see."""
    return _rows(
        "SELECT * FROM entries WHERE player_id = ? AND visibility = 'shared'",
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
