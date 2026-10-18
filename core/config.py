"""Model and Portkey configuration.

Loads .env from the repo folder and every folder above it, nearest wins. That is
what lets the teaching staff keep one .env beside the cloned repos:

    submissions/
    ├── .env          <-- found by the parent walk below
    └── rebound/      <-- this repo
        └── core/config.py

gpt-6-luna needs the Responses API for function tools: chat/completions rejects
tools together with reasoning_effort on this model.
"""

from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = REPO_ROOT / "data" / "playbook.md"

for folder in [REPO_ROOT, *REPO_ROOT.parents]:
    if (folder / ".env").exists():
        load_dotenv(folder / ".env", override=False)

# The course key is for gpt-6-luna only. Shown on the app's Usage page so it is
# never a mystery which model produced a number.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")

# Set PORTKEY_SKIP_CACHE=1 when benchmarking, so Portkey's response cache does not
# make a repeated run look free. Borrowed from hw3/hw4.
SKIP_CACHE = os.getenv("PORTKEY_SKIP_CACHE", "").strip() not in ("", "0", "false")


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is missing. Put it in a .env in this repo, or in the "
            "folder above it. See .env.example."
        )
    return key


def key_is_set() -> bool:
    """For the Usage page's health line — never raises, never returns the key."""
    return bool(os.getenv("PORTKEY_API_KEY", "").strip())


@lru_cache(maxsize=4)
def _model_for_loop(_loop_id: int) -> OpenAIResponsesModel:
    headers = {"x-portkey-provider": "openai"}
    if SKIP_CACHE:
        headers["x-portkey-cache-force-refresh"] = "true"
    client = AsyncOpenAI(
        api_key=require_api_key(),
        base_url=PORTKEY_BASE_URL,
        default_headers=headers,
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def build_model() -> OpenAIResponsesModel:
    """The model, cached per event loop rather than globally.

    The httpx pool inside the client binds to whichever loop first used it, so
    a single cached client handed to a second loop raises "Event loop is
    closed" — and keeps raising it, because the cache holds the dead one
    forever. Keying on the running loop means a client is only ever reused on
    the loop it was born on.

    In the app there is exactly one loop (see core/aio.py), so this caches to
    a single entry. Scripts that call asyncio.run() more than once get a fresh
    client each time, which costs a connection and saves a crash.
    """
    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = 0
    return _model_for_loop(loop_id)


@lru_cache(maxsize=4)
def _playbook_at(_mtime_ns: int) -> str:
    return PLAYBOOK_PATH.read_text(encoding="utf-8")


def playbook() -> str:
    """The club playbook, identical on every run — until someone edits it.

    Every agent prompt starts with this, so it is cached rather than re-read
    per call, and the identical prefix is what the model's prompt cache keys
    on.

    But this file is meant to be edited: it is the one thing an admin changes
    to change what the agents know. Caching it outright meant a running server
    kept answering from the copy it loaded at startup, so a new section was
    invisible until a restart and the agent would say a term was not in the
    playbook while it was sitting there on disk. Keying the cache on the
    file's mtime picks up an edit on the next call and still never re-reads
    an unchanged file.
    """
    try:
        mtime = PLAYBOOK_PATH.stat().st_mtime_ns
    except OSError:
        mtime = 0
    return _playbook_at(mtime)


def playbook_cache_clear() -> None:
    _playbook_at.cache_clear()


playbook.cache_clear = playbook_cache_clear  # type: ignore[attr-defined]
