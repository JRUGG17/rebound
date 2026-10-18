"""One event loop, running for the life of the process.

Dash callbacks are synchronous and agent calls are not, so the work happens on
worker threads. The obvious way to bridge that is `asyncio.run(...)` inside
each thread — and it breaks on the second call.

`asyncio.run` creates a fresh loop and closes it on the way out. The Portkey
client is built once and cached, and the httpx connection pool underneath it
binds to whichever loop first used it. So the first save works, the loop it
used is destroyed, and every save after that fails with "Event loop is
closed". Intermittently, too, depending on which agent ran first.

The fix is to stop making loops. One loop is started here on a daemon thread
and everything is submitted to it, so the client always sees the loop it was
born on.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_lock = threading.Lock()


def loop() -> asyncio.AbstractEventLoop:
    """The process-wide loop, started on first use."""
    global _loop
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=_loop.run_forever, name="rebound-aio", daemon=True)
            thread.start()
        return _loop


def run(coro: Coroutine[Any, Any, T], *, timeout: float = 180.0) -> T:
    """Run a coroutine on the shared loop and block until it finishes.

    Safe to call from any thread except that loop's own. The timeout is a
    backstop so a hung model call cannot pin a worker thread forever.
    """
    future = asyncio.run_coroutine_threadsafe(coro, loop())
    return future.result(timeout=timeout)
