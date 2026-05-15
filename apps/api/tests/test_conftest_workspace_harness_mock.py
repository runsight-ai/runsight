"""API test fixture workspace harness boundary contract."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path


def _load_api_conftest():
    conftest_path = Path(__file__).parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("api_conftest_module", conftest_path)
    conftest_mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(conftest_mod)
    return conftest_path, conftest_mod


def test_api_conftest_patches_workspace_harness_boundary() -> None:
    conftest_path, _ = _load_api_conftest()
    source = conftest_path.read_text(encoding="utf-8")

    assert "UnixLocalHarness" in source
    assert 'UnixLocalHarness, "run"' in source
    assert 'IsolatedBlockWrapper, "execute"' not in source
    assert "_run_in_subprocess" not in source


def test_api_conftest_in_process_bypass_accepts_workspace_run_request() -> None:
    _, conftest_mod = _load_api_conftest()
    source = inspect.getsource(conftest_mod._bypass_subprocess_isolation)

    assert "WorkspaceRunRequest" in source
    assert "WorkspaceMaterializer" in source
    assert "_worker_envelope(request)" in source
