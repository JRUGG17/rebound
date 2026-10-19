"""The tokenomics section, computed from the ledger rather than estimated.

Every number here except the price comes from real runs recorded in
output/usage_ledger.jsonl. The price is the one thing that cannot be measured
from inside the app: the course key is gateway-only, Portkey returns no cost
in the response or the headers, and the analytics endpoints answer 403. So
the rate is an input, stated plainly, and the output is given across a range
so the conclusion does not rest on guessing it right.

Set the real rate when you have it:
    REBOUND_PRICE_IN=... REBOUND_PRICE_CACHED=... REBOUND_PRICE_OUT=... \
        ./venv/bin/python scripts/tokenomics.py
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import metering  # noqa: E402

# Rates to show, in dollars per million tokens: (label, input, cached input, output).
# Cached input is conventionally a fraction of fresh input; the shape of that
# discount is what the caching work is worth, so it is shown explicitly.
SCENARIOS = [
    ("low",    0.15, 0.015, 0.60),
    ("mid",    0.50, 0.050, 2.00),
    ("high",   2.50, 0.250, 10.00),
]

# What one player's month looks like, from the seeded term: a reflection most
# training days, a recap now and then, a day read back occasionally.
PER_USER_MONTH = {
    "organizer:player": 18,   # a reflection most training days
    "recap:player": 3,        # week, fortnight, month
    "day:player": 4,          # reading a session back
    "lessons:player": 1,      # the thread, once
}
# And what a coach costs, spread over the players they look after.
PER_COACH_MONTH = {
    "organizer:coach": 20,    # a note most days
    "comparison": 6,          # a player review before lessons
    "recap:coach": 4,
    "methodology": 8,         # asking the playbook
}
PLAYERS_PER_COACH = 8


def by_agent(rows: list[dict]) -> dict[str, dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[row["agent"]].append(row)
    out = {}
    for agent, runs in sorted(buckets.items()):
        out[agent] = {
            "calls": len(runs),
            "input": statistics.mean(r["input_tokens"] for r in runs),
            "cached": statistics.mean(r["cached_input_tokens"] for r in runs),
            "output": statistics.mean(r["output_tokens"] for r in runs),
            "seconds": statistics.mean(r["seconds"] for r in runs),
        }
    return out


def cost(fresh: float, cached: float, out: float, rates) -> float:
    _label, r_in, r_cached, r_out = rates
    return (fresh * r_in + cached * r_cached + out * r_out) / 1_000_000


def month_cost(mix: dict[str, int], agents: dict[str, dict], rates) -> float:
    total = 0.0
    for agent, n in mix.items():
        stats = agents.get(agent)
        if not stats:
            continue
        fresh = max(0.0, stats["input"] - stats["cached"])
        total += n * cost(fresh, stats["cached"], stats["output"], rates)
    return total


def main() -> int:
    rows = metering.ledger_rows()
    if not rows:
        print("No runs in the ledger yet.")
        return 1
    agents = by_agent(rows)
    totals = metering.totals()

    print("=" * 74)
    print("Rebound — tokenomics, from real runs")
    print("=" * 74)
    print(f"\n{totals['runs']} calls logged · {totals['total_tokens']:,} tokens · "
          f"{totals['cache_hit_rate'] * 100:.0f}% of input served from cache")

    print("\nPER CALL, BY AGENT (measured)")
    print(f"  {'agent':<22}{'calls':>6}{'input':>9}{'cached':>9}{'fresh':>9}"
          f"{'output':>8}{'secs':>7}")
    for agent, s in agents.items():
        fresh = s["input"] - s["cached"]
        print(f"  {agent:<22}{s['calls']:>6}{s['input']:>9,.0f}{s['cached']:>9,.0f}"
              f"{fresh:>9,.0f}{s['output']:>8,.0f}{s['seconds']:>7.1f}")

    print("\nWHAT CACHING IS WORTH (measured, not modelled)")
    fresh_in = totals["input_tokens"] - totals["cached_input_tokens"]
    print(f"  input tokens billed fresh      {fresh_in:>12,}")
    print(f"  input tokens served from cache {totals['cached_input_tokens']:>12,}")
    print(f"  without prompt caching, every one of those would be a fresh token.")

    configured = metering.PRICES_CONFIGURED
    scenarios = SCENARIOS[:]
    if configured:
        scenarios.insert(0, ("ACTUAL", metering.PRICE_PER_MTOK_INPUT,
                             metering.PRICE_PER_MTOK_CACHED_INPUT,
                             metering.PRICE_PER_MTOK_OUTPUT))

    print("\nCOST — the rate is the only thing here that is not measured")
    if not configured:
        print("  No rate set, so three plausible ones are shown. Set")
        print("  REBOUND_PRICE_IN / _CACHED / _OUT to pin it to the real one.")
    print(f"\n  {'rate':<8}{'$/Mtok in':>11}{'cached':>9}{'out':>8}"
          f"{'1 player/mo':>14}{'1 coach/mo':>13}{'100 users':>12}{'10k users':>12}")
    for sc in scenarios:
        label, r_in, r_cached, r_out = sc
        player = month_cost(PER_USER_MONTH, agents, sc)
        coach = month_cost(PER_COACH_MONTH, agents, sc)
        # A club is players plus a coach for every eight of them.
        per_user = player + coach / PLAYERS_PER_COACH
        print(f"  {label:<8}{r_in:>11.2f}{r_cached:>9.3f}{r_out:>8.2f}"
              f"{player:>14.4f}{coach:>13.4f}"
              f"{per_user * 100:>12.2f}{per_user * 10_000:>12.0f}")

    print("\n  Columns are dollars per month. 'per user' folds in one coach's share")
    print(f"  across {PLAYERS_PER_COACH} players, which is roughly a squad.")
    print("\n" + "=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
