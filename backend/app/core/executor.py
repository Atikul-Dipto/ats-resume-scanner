"""The one seam for CPU-bound work (PDF/DOCX parsing, PDF rendering).

Today: a worker thread, behind a semaphore so a burst of uploads can't run
unbounded parses in parallel and exhaust a small instance's memory. The event
loop stays free to serve health checks and job searches meanwhile.

At higher load this is the function to change — to a process pool or a
queue-backed worker — without touching any route. See ARCHITECTURE.md.
"""

import asyncio
from collections.abc import Callable

from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().parse_concurrency)
    return _semaphore


async def run_cpu_bound[T](fn: Callable[..., T], *args, **kwargs) -> T:
    async with _get_semaphore():
        return await run_in_threadpool(fn, *args, **kwargs)


def reset() -> None:
    """Called at startup: an asyncio.Semaphore binds to the event loop that first
    waits on it, so each app lifespan (and each test client) gets a fresh one."""
    global _semaphore
    _semaphore = None
