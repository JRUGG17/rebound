"""Token and cost metering.

Nothing in the course repo reads cached-token counts or computes a dollar cost,
so this is written from scratch. Every agent run appends one row to a JSONL
ledger from the very first run, which is where the report's tokenomics numbers
come from — measured, not estimated.

Field names differ across pydantic-ai versions and across providers, so every
read here is defensive: unknown shapes degrade to zero rather than crashing a
user-facing run. Run scripts/check_model.py to dump the real shape.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import MODEL_NAME, REPO_ROOT

LEDGER_PATH = Path(os.getenv("REBOUND_LEDGER", REPO_ROOT / "output" / "usage_ledger.jsonl"))
_LEDGER_LOCK = threading.Lock()

# --------------------------------------------------------------------------
# Prices, in US dollars per million tokens.
#
# TODO(jamie): confirm these against the Portkey dashboard before the report.
# They are the single number the whole tokenomics section rests on, and a wrong
# rate makes every figure in it wrong. Override without editing code by setting
# REBOUND_PRICE_IN / REBOUND_PRICE_CACHED / REBOUND_PRICE_OUT.
# --------------------------------------------------------------------------
PRICE_PER_MTOK_INPUT = float(os.getenv("REBOUND_PRICE_IN", "0.0"))
PRICE_PER_MTOK_CACHED_INPUT = float(os.getenv("REBOUND_PRICE_CACHED", "0.0"))
PRICE_PER_MTOK_OUTPUT = float(os.getenv("REBOUND_PRICE_OUT", "0.0"))

PRICES_CONFIGURED = any(
    (PRICE_PER_MTOK_INPUT, PRICE_PER_MTOK_CACHED_INPUT, PRICE_PER_MTOK_OUTPUT)
)

# Candidate attribute / key names for each count, newest first. pydantic-ai has
# moved these around; OpenAI reports cached reads under prompt_tokens_details.
_INPUT_KEYS = ("input_tokens", "request_tokens", "prompt_tokens")
_OUTPUT_KEYS = ("output_tokens", "response_tokens", "completion_tokens")
_CACHED_KEYS = ("cache_read_tokens", "cached_tokens", "cache_read_input_tokens")
_REASONING_KEYS = ("reasoning_tokens",)


def _first_int(source: Any, keys: tuple[str, ...]) -> int:
    """First present, non-null value among `keys`, read as an int.

    Looks at attributes and, for dicts or objects carrying a `details` mapping,
    at those keys too.
    """
    if source is None:
        return 0
    details = getattr(source, "details", None)
    if not isinstance(details, dict):
        details = {}
    extra = getattr(source, "prompt_tokens_details", None) or {}
    if not isinstance(extra, dict):
        extra = {k: getattr(extra, k) for k in dir(extra) if not k.startswith("_")}

    for key in keys:
        for holder in (source, details, extra):
            value = holder.get(key) if isinstance(holder, dict) else getattr(holder, key, None)
            if isinstance(value, (int, float)):
                return int(value)
    return 0


@dataclass
class RunUsage:
    """One agent run's measured usage."""

    agent: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    requests: int = 0
    tool_calls: int = 0
    seconds: float = 0.0
    model: str = MODEL_NAME
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def fresh_input_tokens(self) -> int:
        """Input tokens actually billed at the full rate (total minus cache hits)."""
        return max(0, self.input_tokens - self.cached_input_tokens)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cache_hit_rate(self) -> float:
        """Share of input tokens served from cache, 0.0–1.0."""
        return self.cached_input_tokens / self.input_tokens if self.input_tokens else 0.0

    @property
    def cost_usd(self) -> float:
        return (
            self.fresh_input_tokens * PRICE_PER_MTOK_INPUT
            + self.cached_input_tokens * PRICE_PER_MTOK_CACHED_INPUT
            + self.output_tokens * PRICE_PER_MTOK_OUTPUT
        ) / 1_000_000

    def as_row(self) -> dict:
        row = asdict(self)
        row.update(
            fresh_input_tokens=self.fresh_input_tokens,
            total_tokens=self.total_tokens,
            cache_hit_rate=round(self.cache_hit_rate, 4),
            cost_usd=round(self.cost_usd, 8),
            prices_configured=PRICES_CONFIGURED,
        )
        return row


def read_usage(usage: Any, *, agent: str, seconds: float = 0.0) -> RunUsage:
    """Turn whatever pydantic-ai handed back into a RunUsage."""
    if callable(usage):
        usage = usage()
    return RunUsage(
        agent=agent,
        input_tokens=_first_int(usage, _INPUT_KEYS),
        cached_input_tokens=_first_int(usage, _CACHED_KEYS),
        output_tokens=_first_int(usage, _OUTPUT_KEYS),
        reasoning_tokens=_first_int(usage, _REASONING_KEYS),
        requests=_first_int(usage, ("requests",)),
        tool_calls=_first_int(usage, ("tool_calls",)),
        seconds=round(seconds, 2),
    )


def record(run: RunUsage) -> RunUsage:
    """Append one run to the ledger. Never raises into a user-facing call."""
    try:
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(run.as_row())
        with _LEDGER_LOCK, LEDGER_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    return run


def ledger_rows() -> list[dict]:
    """Every run recorded so far. Bad lines are skipped, not fatal."""
    if not LEDGER_PATH.exists():
        return []
    rows = []
    for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def totals() -> dict:
    """Roll the ledger up for the Usage page."""
    rows = ledger_rows()
    if not rows:
        return {"runs": 0, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
                "total_tokens": 0, "cost_usd": 0.0, "cache_hit_rate": 0.0, "seconds": 0.0}
    total_input = sum(r.get("input_tokens", 0) for r in rows)
    total_cached = sum(r.get("cached_input_tokens", 0) for r in rows)
    return {
        "runs": len(rows),
        "input_tokens": total_input,
        "cached_input_tokens": total_cached,
        "output_tokens": sum(r.get("output_tokens", 0) for r in rows),
        "total_tokens": sum(r.get("total_tokens", 0) for r in rows),
        "cost_usd": round(sum(r.get("cost_usd", 0.0) for r in rows), 6),
        "cache_hit_rate": round(total_cached / total_input, 4) if total_input else 0.0,
        "seconds": round(sum(r.get("seconds", 0.0) for r in rows), 1),
    }


class Timer:
    """`with Timer() as t:` ... `t.seconds`."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.seconds = 0.0
        return self

    def __exit__(self, *exc) -> None:
        self.seconds = time.perf_counter() - self._start
