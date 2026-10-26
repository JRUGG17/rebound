"""Phase 4 check: the Comparison agent against the seeded roster.

Each player is seeded so that exactly one thing should be found, including
Jonah, who is seeded clean. Costs money.

Run:  ./venv/bin/python scripts/check_comparison.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import analysis, db, metering  # noqa: E402
from core.agents import comparison  # noqa: E402
from data import seed  # noqa: E402


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{f'  — {detail}' if detail else ''}")
    if not ok:
        check.failed += 1
    return ok


check.failed = 0


def show(review, usage) -> None:
    print(f"      [{usage.input_tokens} in / {usage.cached_input_tokens} cached / "
          f"{usage.output_tokens} out / {usage.seconds}s]")
    for finding in review.findings:
        print(f"\n      ({finding.kind}, {finding.confidence})")
        print(f"      {finding.headline}")
        print(f"        evidence: {finding.evidence}")
        if finding.timing_caution:
            print(f"        TIMING:   {finding.timing_caution}")
        print(f"        to coach: {finding.for_the_coach}")
    print()


async def maya() -> None:
    print("\n[1] Maya — a chronic cue and a lob that stops transferring")
    review, usage = await comparison.review_player("maya")
    show(review, usage)
    kinds = {f.kind for f in review.findings}
    check("found the chronic cue", "chronic_cue" in kinds, str(kinds))
    check("found a transfer gap", "transfer_gap" in kinds, str(kinds))
    gap = next((f for f in review.findings if f.kind == "transfer_gap"), None)
    if gap:
        check("named the rung where it stops", gap.rung in
              ("pattern", "conditioned_game", "match"), str(gap.rung))
    blob = " ".join(f.evidence for f in review.findings)
    check("used real counts, not vague ones",
          "3" in blob or "three" in blob.lower())


async def dev() -> None:
    print("\n[2] Dev — two coaches, opposite advice, week 6")
    review, usage = await comparison.review_player("dev")
    show(review, usage)
    check("found the conflict",
          "coach_conflict" in {f.kind for f in review.findings})


async def ellie() -> None:
    print("\n[3] Ellie — a real problem that is the wrong problem for this month")
    review, usage = await comparison.review_player("ellie")
    show(review, usage)
    check("raised a timing caution",
          any(f.timing_caution for f in review.findings),
          "no finding carried one")


async def jonah() -> None:
    print("\n[4] Jonah — the control. Nothing is wrong with him.")
    review, usage = await comparison.review_player("jonah")
    show(review, usage)
    bad = [f for f in review.findings
           if f.kind in ("transfer_gap", "chronic_cue", "coach_conflict")]
    check("did not invent a problem", not bad,
          f"invented: {[f.kind for f in bad]}")


def arithmetic() -> None:
    print("\n[5] The counting, which is Python and not the model")
    runs = analysis.cue_runs("maya")
    chronic = [r for r in runs if r.is_chronic]
    check("Maya has a chronic cue by the numbers", bool(chronic),
          ", ".join(f"{r.canonical} x{r.count} over {r.span_weeks}wk" for r in chronic))
    jonah_chronic = [r for r in analysis.cue_runs("jonah") if r.is_chronic]
    check("Jonah has none", not jonah_chronic)
    grid = analysis.matrix("maya")
    check("the shot x rung matrix builds", bool(grid), ", ".join(grid))
    # Boundedness, not compression. The digest is deliberately larger than
    # the raw text it covers — it wraps each line in a week, a rung, an
    # author and a count, and those counts are the whole reason the agent
    # can be trusted with numbers. What it must not do is grow without
    # limit as a career accumulates, so the caps in analysis.digest are
    # what this checks: every player stays well under a fixed ceiling even
    # with a full block on record.
    CEILING = 12000
    worst, size = max(
        ((p["id"], len(analysis.digest(p["id"]))) for p in db.people("player")),
        key=lambda x: x[1])
    check("the digest stays bounded for every player", size < CEILING,
          f"largest is {worst} at {size} chars, ceiling {CEILING}")


async def main() -> int:
    print("=" * 70)
    print("Rebound — Comparison agent")
    print("=" * 70)
    seed.build()
    before = metering.totals()
    arithmetic()
    await maya()
    await dev()
    await ellie()
    await jonah()
    after = metering.totals()
    print("-" * 70)
    print(f"  {after['runs'] - before['runs']} calls, "
          f"{after['total_tokens'] - before['total_tokens']:,} tokens, "
          f"{after['cache_hit_rate'] * 100:.0f}% cached overall")
    print("ALL PASS" if not check.failed else f"{check.failed} FAILED")
    return 1 if check.failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
