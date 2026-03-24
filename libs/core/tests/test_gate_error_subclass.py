"""
Tests for RUN-254 — SUPERSEDED by RUN-268.

GateError was deleted in RUN-268. GateBlock now returns exit_handle="pass"/"fail"
instead of raising. All original RUN-254 tests have been removed.

See tests/unit/test_gate_exit_handle.py for the replacement tests.
"""
