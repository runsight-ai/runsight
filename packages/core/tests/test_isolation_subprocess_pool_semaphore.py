"""Subprocess pool concurrency behavior."""

import asyncio

import pytest

# Shared fixtures
from isolation_dispatch_delegate_helpers import (
    _make_result_envelope,
)

pytestmark = pytest.mark.real_subprocess_isolation


class TestSubprocessPoolSemaphore:
    """A semaphore limits concurrent subprocess execution for downstream blocks."""

    def test_pool_importable(self):
        """SubprocessPool is importable from runsight_core.isolation.pool."""
        from runsight_core.isolation.pool import SubprocessPool

        assert SubprocessPool is not None

    def test_default_max_concurrent_subprocesses_is_10(self):
        """The subprocess pool semaphore defaults to max_concurrent_subprocesses=10."""
        from runsight_core.isolation.pool import SubprocessPool

        pool = SubprocessPool()
        assert pool.max_concurrent_subprocesses == 10

    def test_custom_max_concurrent_subprocesses(self):
        """The semaphore limit can be configured."""
        from runsight_core.isolation.pool import SubprocessPool

        pool = SubprocessPool(max_concurrent_subprocesses=5)
        assert pool.max_concurrent_subprocesses == 5

    def test_semaphore_limits_concurrent_execution(self):
        """When max_concurrent_subprocesses=2 and 4 blocks try to run,
        at most 2 execute concurrently."""
        from runsight_core.isolation.pool import SubprocessPool

        pool = SubprocessPool(max_concurrent_subprocesses=2)
        max_concurrent_seen = 0
        current_concurrent = 0

        async def fake_run(block_id: str):
            nonlocal max_concurrent_seen, current_concurrent
            current_concurrent += 1
            if current_concurrent > max_concurrent_seen:
                max_concurrent_seen = current_concurrent
            await asyncio.sleep(0.05)
            current_concurrent -= 1
            return _make_result_envelope(block_id=block_id)

        async def run_test():
            worker_ids = [
                "analysis_worker",
                "summary_worker",
                "review_worker",
                "publish_worker",
            ]
            tasks = [pool.submit(fake_run, worker_id) for worker_id in worker_ids]
            await asyncio.gather(*tasks)

        asyncio.get_event_loop().run_until_complete(run_test())
        assert max_concurrent_seen <= 2, f"Expected at most 2 concurrent, saw {max_concurrent_seen}"

    def test_pool_has_submit_method(self):
        """SubprocessPool must have a submit method for downstream block execution."""
        from runsight_core.isolation.pool import SubprocessPool

        pool = SubprocessPool(max_concurrent_subprocesses=10)
        assert hasattr(pool, "submit"), (
            "SubprocessPool must have a submit method for downstream blocks"
        )
