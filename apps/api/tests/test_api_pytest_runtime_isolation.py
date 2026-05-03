"""Governance tests for the API pytest runtime workspace and environment.

Owner: API test harness.
Boundary: API tests must never inherit developer runtime state from repo-root
or shell-provided RUNSIGHT_* paths, DB URLs, or provider credentials.
Exit criteria: replace these assertions only if pytest runtime-root creation
moves into a documented shared test plugin with equivalent isolation coverage.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SECRET_ENV_FRAGMENTS = (
    "API_KEY",
    "ACCESS_KEY",
    "CREDENTIAL",
    "PASSWORD",
    "PRIVATE_KEY",
    "SECRET",
    "TOKEN",
)
RUNSIGHT_ENV_ALLOWLIST = {"RUNSIGHT_BASE_PATH", "RUNSIGHT_DB_URL"}
SECRET_NAME_FALSE_POSITIVE_ALLOWLIST = {"TIKTOKEN_CACHE_DIR"}


class TestApiPytestRuntimeIsolationGovernance:
    """API pytest owns its runtime workspace and database path."""

    def test_api_pytest_base_path_is_session_owned_temp_workspace(self):
        base_path = Path(os.environ["RUNSIGHT_BASE_PATH"]).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()

        assert base_path.is_dir()
        assert base_path.name.startswith("runsight-api-pytest-")
        assert base_path.parent == temp_root
        assert base_path != REPO_ROOT
        assert REPO_ROOT not in base_path.parents

    def test_api_pytest_database_path_stays_inside_session_runtime_root(self):
        base_path = Path(os.environ["RUNSIGHT_BASE_PATH"]).resolve()
        db_url = os.environ["RUNSIGHT_DB_URL"]

        assert db_url.startswith("sqlite:///")
        db_path = Path(db_url.removeprefix("sqlite:///")).resolve()
        assert db_path == base_path / ".runsight" / "runsight.db"

    def test_api_pytest_scrubs_inherited_secret_bearing_environment(self):
        leaked_names = [
            name
            for name in os.environ
            if any(fragment in name for fragment in SECRET_ENV_FRAGMENTS)
            and name not in SECRET_NAME_FALSE_POSITIVE_ALLOWLIST
        ]

        assert leaked_names == []

    def test_api_pytest_allows_only_pytest_owned_runsight_environment(self):
        runsight_names = {name for name in os.environ if name.startswith("RUNSIGHT_")}

        assert runsight_names == RUNSIGHT_ENV_ALLOWLIST
