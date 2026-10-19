"""The tokenomics section, computed from the ledger rather than estimated.

Token counts come from real runs recorded in output/usage_ledger.jsonl.
Rates are the published gpt-6-luna prices from the course tokenomics
lecture, which cites https://developers.openai.com/api/docs/pricing —
input $0.10, cached $0.01, cache write $0.125, output $0.50 per million.

The accounting rule that matters: input_tokens already includes cache reads
and cache writes, so both come off before the remainder is charged at the
input rate. A cache write costs more than a plain input token, so lumping
them together understates the bill.
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
# The real rate, plus gpt-6-astra for comparison — the report should be able
# to say what the model choice is worth.
SCENARIOS = [
    ("luna",  0.10, 0.01, 0.125, 0.50),
    ("astra", 10.00, 1.00, 12.50, 50.00),
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
            "written": statistics.mean(r.get("cache_write_tokens", 0) for r in runs),
            "fresh": statistics.mean(
                max(0, r["input_tokens"] - r["cached_input_tokens"]
                    - r.get("cache_write_tokens", 0)) for r in runs),
            "output": statistics.mean(r["output_tokens"] for r in runs),
            "seconds": statistics.mean(r["seconds"] for r in runs),
        }
    return out


def cost(fresh: float, cached: float, written: float, out: float, rates) -> float:
    _label, r_in, r_cached, r_write, r_out = rates
    return (fresh * r_in + cached * r_cached
            + written * r_write + out * r_out) / 1_000_000


def month_cost(mix: dict[str, int], agents: dict[str, dict], rates) -> float:
    total = 0.0
    for agent, n in mix.items():
        stats = agents.get(agent)
        if not stats:
            continue
        total += n * cost(stats["fresh"], stats["cached"], stats["written"],
                          stats["output"], rates)
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

    luna = SCENARIOS[0]
    print("\nPER CALL, BY AGENT (measured)")
    print(f"  {'agent':<22}{'calls':>6}{'input':>9}{'cached':>8}{'write':>7}"
          f"{'fresh':>8}{'output':>8}{'secs':>6}{'$/call':>10}")
    for agent, s in agents.items():
        per_call = cost(s["fresh"], s["cached"], s["written"], s["output"], luna)
        print(f"  {agent:<22}{s['calls']:>6}{s['input']:>9,.0f}{s['cached']:>8,.0f}"
              f"{s['written']:>7,.0f}{s['fresh']:>8,.0f}{s['output']:>8,.0f}"
              f"{s['seconds']:>6.1f}{per_call:>10.5f}")

    print("\nWHAT CACHING IS WORTH (measured, not modelled)")
    cached_tok = totals["cached_input_tokens"]
    written = totals.get("cache_write_tokens", 0)
    fresh_in = totals["input_tokens"] - cached_tok - written
    print(f"  input billed fresh        {fresh_in:>12,}")
    print(f"  input served from cache   {cached_tok:>12,}")
    print(f"  cache writes              {written:>12,}")
    saved = cached_tok * (luna[1] - luna[2]) / 1_000_000
    print(f"  those cache reads cost ${cached_tok * luna[2] / 1_000_000:.4f} "
          f"instead of ${cached_tok * luna[1] / 1_000_000:.4f} — "
          f"${saved:.4f} saved so far")
    print(f"  total spend to date       ${totals['cost_usd']:>11.4f}")

    print("\nCOST AT SCALE")
    print(f"\n  {'model':<8}{'$/Mtok in':>11}{'cached':>9}{'write':>8}{'out':>8}"
          f"{'1 player/mo':>14}{'1 coach/mo':>13}{'100 users':>12}{'10k users':>12}")
    for sc in SCENARIOS:
        label, r_in, r_cached, r_write, r_out = sc
        player = month_cost(PER_USER_MONTH, agents, sc)
        coach = month_cost(PER_COACH_MONTH, agents, sc)
        # A club is players plus a coach for every eight of them.
        per_user = player + coach / PLAYERS_PER_COACH
        print(f"  {label:<8}{r_in:>11.2f}{r_cached:>9.2f}{r_write:>8.3f}{r_out:>8.2f}"
              f"{player:>14.4f}{coach:>13.4f}"
              f"{per_user * 100:>12.2f}{per_user * 10_000:>12.0f}")

    print("\n  Columns are dollars per month. 'per user' folds in one coach's share")
    print(f"  across {PLAYERS_PER_COACH} players, which is roughly a squad.")
    print("  Rates: course tokenomics lecture, citing developers.openai.com/api/docs/pricing")
    print("\n" + "=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
