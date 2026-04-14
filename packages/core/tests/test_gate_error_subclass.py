"""Tests for RUN-254 — superseded by RUN-268."""

import pytest


def test_gate_error_subclass_tests_retired() -> None:
    pytest.skip("GateError was removed in RUN-268; exit-handle tests cover the replacement.")
