"""SubprocessPool — semaphore-based concurrency limiter for isolated block execution."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class SubprocessPool:
    """Limits concurrent subprocess execution via an asyncio.Semaphore."""

    def __init__(self, max_concurrent_subprocesses: int = 10) -> None:
        self.max_concurrent_subprocesses = max_concurrent_subprocesses
        self._semaphore = asyncio.Semaphore(max_concurrent_subprocesses)

    async def submit(self, fn: Callable[..., Awaitable[T]], *args: Any) -> T:
        """Run *fn(*args)* under the concurrency semaphore."""
        async with self._semaphore:
            return await fn(*args)
