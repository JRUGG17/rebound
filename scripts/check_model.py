"""Phase 1 smoke test.

Answers three questions before anything is built on top of them:

  1. Is the .env found, including when it sits one folder above the repo?
  2. Which model-name spelling does the course key actually accept?
  3. What shape is the usage object, so metering reads the right fields?

Run:  ./venv/bin/python scripts/check_model.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic_ai import Agent  # noqa: E402

from core import config, metering  # noqa: E402

CANDIDATE_NAMES = ["gpt-6-luna", "gpt-6 luna"]


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{f'  — {detail}' if detail else ''}")
    if not ok:
        check.failed += 1
    return ok


check.failed = 0


def env_report() -> None:
    print("\n[1] Environment")
    found = [f for f in [config.REPO_ROOT, *config.REPO_ROOT.parents] if (f / ".env").exists()]
    check("a .env was found", bool(found), str(found[0]) if found else "none on the parent walk")
    if found and found[0] != config.REPO_ROOT:
        print(f"        (it is {len(found[0].parts) and 'above'} the repo — the grading layout)")
    check("PORTKEY_API_KEY is set", config.key_is_set())
    check("playbook.md is readable", config.PLAYBOOK_PATH.exists(), str(config.PLAYBOOK_PATH))
    if config.PLAYBOOK_PATH.exists():
        words = len(config.playbook().split())
        check("playbook is long enough to cache", words > 700, f"{words} words")


async def try_model(name: str) -> tuple[bool, object, str]:
    """One tiny real call against `name`. Returns (ok, usage, error)."""
    import openai
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    client = openai.AsyncOpenAI(
        api_key=config.require_api_key(),
        base_url=config.PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )
    model = OpenAIResponsesModel(name, provider=OpenAIProvider(openai_client=client))
    agent = Agent(model, system_prompt="Reply with exactly one word.")
    try:
        result = await agent.run("Say: ok")
        usage = result.usage() if callable(result.usage) else result.usage
        return True, usage, ""
    except Exception as exc:  # noqa: BLE001 — we are probing, any failure is data
        return False, None, f"{type(exc).__name__}: {str(exc)[:160]}"


async def model_report() -> str | None:
    print("\n[2] Model name")
    winner = None
    for name in CANDIDATE_NAMES:
        ok, _usage, err = await try_model(name)
        print(f"  {'PASS' if ok else 'fail'}  {name!r}{'' if ok else f'  — {err}'}")
        if ok and winner is None:
            winner = name
    check("at least one spelling works", winner is not None)
    if winner:
        print(f"\n  -> use MODEL_NAME = {winner!r}")
        if winner != config.MODEL_NAME:
            print(f"  !! config.py currently has {config.MODEL_NAME!r} — change it.")
    return winner


async def usage_report(name: str) -> None:
    print("\n[3] Usage object shape")
    with metering.Timer() as timer:
        ok, usage, err = await try_model(name)
    if not check("a run returned usage", ok, err):
        return

    print(f"\n  raw type: {type(usage).__name__}")
    for attr in sorted(a for a in dir(usage) if not a.startswith("_")):
        value = getattr(usage, attr, None)
        if not callable(value):
            print(f"    .{attr} = {value!r}")

    run = metering.read_usage(usage, agent="smoke-test", seconds=timer.seconds)
    print(f"\n  parsed: in={run.input_tokens} cached={run.cached_input_tokens} "
          f"out={run.output_tokens} reasoning={run.reasoning_tokens}")
    check("input tokens were read", run.input_tokens > 0)
    check("output tokens were read", run.output_tokens > 0)
    if not metering.PRICES_CONFIGURED:
        print("  note: prices are still 0.0 — cost stays $0 until they are set.")
    metering.record(run)
    check("ledger wrote a row", metering.totals()["runs"] > 0, str(metering.LEDGER_PATH))


async def main() -> int:
    print("=" * 64)
    print("Rebound — Phase 1 smoke test")
    print("=" * 64)
    env_report()
    if not config.key_is_set():
        print("\nNo API key, stopping before the live calls.")
        return 1
    winner = await model_report()
    if winner:
        await usage_report(winner)
    print("\n" + "=" * 64)
    print("ALL PASS" if not check.failed else f"{check.failed} FAILED")
    return 1 if check.failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
