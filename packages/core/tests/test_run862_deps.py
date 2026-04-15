"""
RUN-862: Verify dependency manifest correctness for packages/core.

These tests inspect pyproject.toml directly — no imports, no installs required.
"""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def _load() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_no_openai_in_core_deps() -> None:
    """openai must not appear in [project.dependencies] — litellm owns LLM calls."""
    data = _load()
    deps: list[str] = data["project"]["dependencies"]
    names = [d.split(">=")[0].split("==")[0].split("[")[0].strip() for d in deps]
    assert "openai" not in names, f"openai found in core deps: {deps}"


def test_pyyaml_in_core_deps() -> None:
    """pyyaml must be listed in [project.dependencies] — core imports yaml throughout."""
    data = _load()
    deps: list[str] = data["project"]["dependencies"]
    names = [d.split(">=")[0].split("==")[0].split("[")[0].strip() for d in deps]
    assert "pyyaml" in names, f"pyyaml missing from core deps: {deps}"


def test_no_respx_in_core_dev_deps() -> None:
    """respx must not appear in [project.optional-dependencies.dev] — never imported."""
    data = _load()
    dev_deps: list[str] = data["project"]["optional-dependencies"]["dev"]
    names = [d.split(">=")[0].split("==")[0].split("[")[0].strip() for d in dev_deps]
    assert "respx" not in names, f"respx found in dev deps: {dev_deps}"
