"""Legacy EvalObserver suite entrypoint.

Behavior coverage lives in focused owner suites:

- test_eval_observer_basics.py
- test_eval_observer_assertion_execution.py
- test_eval_observer_stream_emission.py
- test_eval_observer_baseline_aggregate.py
- test_eval_observer_child_ownership.py
"""

from __future__ import annotations

import importlib


def test_eval_observer_behavior_owner_suites_import() -> None:
    """The legacy targeted command remains valid while behavior lives in owner suites."""
    for module_name in [
        "test_eval_observer_basics",
        "test_eval_observer_assertion_execution",
        "test_eval_observer_stream_emission",
        "test_eval_observer_baseline_aggregate",
        "test_eval_observer_child_ownership",
    ]:
        assert importlib.import_module(module_name) is not None
