"""Red tests for RUN-822: embedded identity must drive YAML repository lookups."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

import pytest
import yaml
from pydantic import BaseModel

from runsight_api.data.filesystem._base_yaml_repo import BaseYamlRepository
from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.domain.errors import RunsightError, SoulNotFound


class DummyEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "allow"}


class DummyNotFound(RunsightError):
    pass


class DummyRepository(BaseYamlRepository[DummyEntity]):
    entity_type = DummyEntity
    subdir = "dummies"
    not_found_error = DummyNotFound
    entity_label = "Dummy"


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_list_all_does_not_synthesize_missing_id_from_filename_stem() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = DummyRepository(base_path=tmpdir)
        _write_yaml(repo.entity_dir / "auto-id.yaml", {"name": "No ID"})

        assert repo.list_all() == []


def test_get_by_id_does_not_resolve_embedded_id_in_other_yaml_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = DummyRepository(base_path=tmpdir)
        _write_yaml(repo.entity_dir / "legacy-name.yaml", {"id": "real-id", "name": "Legacy"})

        assert repo.get_by_id("real-id") is None


def test_update_does_not_retarget_embedded_id_match_in_other_yaml_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = DummyRepository(base_path=tmpdir)
        _write_yaml(repo.entity_dir / "legacy-name.yaml", {"id": "real-id", "name": "Legacy"})

        with pytest.raises(DummyNotFound):
            repo.update("real-id", {"name": "Updated"})


def test_soul_repository_does_not_resolve_embedded_id_from_filename_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)
        _write_yaml(
            repo.entity_dir / "gate_evaluator.yaml",
            {
                "id": "gate_eval_1",
                "kind": "soul",
                "name": "Quality Gate Evaluator",
                "role": "Quality Gate Evaluator",
                "system_prompt": "Check quality.",
            },
        )

        assert repo.get_by_id("gate_eval_1") is None


def test_soul_repository_update_does_not_retarget_embedded_id_match() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)
        _write_yaml(
            repo.entity_dir / "gate_evaluator.yaml",
            {
                "id": "gate_eval_1",
                "kind": "soul",
                "name": "Quality Gate Evaluator",
                "role": "Quality Gate Evaluator",
                "system_prompt": "Check quality.",
            },
        )

        with pytest.raises(SoulNotFound):
            repo.update(
                "gate_eval_1",
                {
                    "kind": "soul",
                    "name": "Quality Gate Evaluator",
                    "role": "Updated Gate",
                    "system_prompt": "Check quality.",
                },
            )
