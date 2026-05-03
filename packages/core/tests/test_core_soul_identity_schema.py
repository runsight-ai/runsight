from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from runsight_core.isolation.envelope import SoulEnvelope
from runsight_core.isolation.worker_support import reconstruct_soul
from runsight_core.primitives import Soul
from runsight_core.yaml.discovery import SoulScanner
from runsight_core.yaml.schema import RunsightWorkflowFile, SoulDef


def _soul_payload(*, soul_id: str, name: str, role: str = "Researcher", kind: str = "soul") -> dict:
    return {
        "id": soul_id,
        "kind": kind,
        "name": name,
        "role": role,
        "system_prompt": "Do the thing.",
    }


def _workflow_payload(*, souls: dict[str, dict]) -> dict:
    return {
        "version": "1.0",
        "id": "inline_soul_flow",
        "kind": "workflow",
        "workflow": {"name": "inline_soul_flow", "entry": "draft", "transitions": []},
        "souls": souls,
        "blocks": {
            "draft": {
                "type": "linear",
                "soul_ref": "writer",
            }
        },
    }


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


class TestSoulDefIdentity:
    def test_valid_souldef_requires_embedded_identity(self) -> None:
        soul = SoulDef.model_validate(
            _soul_payload(soul_id="researcher", name="Researcher", role="Researcher")
        )

        assert soul.id == "researcher"
        assert soul.kind == "soul"
        assert soul.name == "Researcher"
        assert soul.role == "Researcher"

    @pytest.mark.parametrize(
        ("payload", "expected_field"),
        [
            (
                {
                    "id": "researcher",
                    "kind": "soul",
                    "role": "Researcher",
                    "system_prompt": "Do the thing.",
                },
                "name",
            ),
            (
                {
                    "id": "researcher",
                    "name": "Researcher",
                    "role": "Researcher",
                    "system_prompt": "Do the thing.",
                },
                "kind",
            ),
        ],
    )
    def test_missing_identity_fields_are_rejected(self, payload: dict, expected_field: str) -> None:
        with pytest.raises(ValidationError):
            SoulDef.model_validate(payload)

    @pytest.mark.parametrize("kind", ["tool", "workflow", "provider"])
    def test_wrong_kind_is_rejected(self, kind: str) -> None:
        with pytest.raises(ValidationError):
            SoulDef.model_validate(
                _soul_payload(soul_id="researcher", name="Researcher", kind=kind)
            )

    @pytest.mark.parametrize("soul_id", ["Research Soul", "s", "soul/http"])
    def test_invalid_soul_id_is_rejected(self, soul_id: str) -> None:
        with pytest.raises(ValidationError):
            SoulDef.model_validate(_soul_payload(soul_id=soul_id, name="Researcher"))


class TestSoulPrimitiveIdentity:
    def test_valid_soul_requires_embedded_identity(self) -> None:
        soul = Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research the topic.",
        )

        assert soul.id == "researcher"
        assert soul.kind == "soul"
        assert soul.name == "Researcher"
        assert soul.role == "Researcher"

    def test_missing_kind_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Soul(
                id="researcher",
                name="Researcher",
                role="Researcher",
                system_prompt="Research the topic.",
            )

    def test_missing_name_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Soul(
                id="researcher",
                kind="soul",
                role="Researcher",
                system_prompt="Research the topic.",
            )


class TestSoulScannerIdentity:
    def test_scanner_uses_embedded_soul_id(self, tmp_path: Path) -> None:
        soul_path = tmp_path / "custom" / "souls" / "researcher.yaml"
        _write_yaml(soul_path, _soul_payload(soul_id="researcher", name="Researcher"))

        scan_index = SoulScanner(tmp_path).scan()
        soul = scan_index.ids()["researcher"]

        assert soul.id == "researcher"
        assert soul.kind == "soul"
        assert soul.name == "Researcher"

    @pytest.mark.parametrize("soul_id", ["researcher-v2", "researcher_embedded"])
    def test_scanner_rejects_filename_stem_mismatch(self, tmp_path: Path, soul_id: str) -> None:
        soul_path = tmp_path / "custom" / "souls" / "researcher.yaml"
        _write_yaml(soul_path, _soul_payload(soul_id=soul_id, name="Researcher"))

        with pytest.raises((ValidationError, ValueError)):
            SoulScanner(tmp_path).scan()

    def test_scanner_rejects_duplicate_embedded_ids_across_files(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "custom" / "souls" / "researcher.yaml",
            _soul_payload(soul_id="researcher", name="Researcher"),
        )
        _write_yaml(
            tmp_path / "custom" / "souls" / "researcher_copy.yaml",
            _soul_payload(soul_id="researcher", name="Researcher Copy"),
        )

        with pytest.raises((ValidationError, ValueError)):
            SoulScanner(tmp_path).scan()


class TestWorkerSoulReconstructionIdentity:
    def test_reconstruct_soul_requires_explicit_name(self) -> None:
        soul_env = SoulEnvelope(
            id="researcher",
            role="Researcher",
            system_prompt="Research the topic.",
            model_name="gpt-4o-mini",
            max_tool_iterations=5,
        )

        with pytest.raises(ValidationError):
            reconstruct_soul(soul_env)


class TestInlineSoulIdentity:
    def test_inline_soul_requires_name_and_kind(self) -> None:
        with pytest.raises(ValidationError):
            RunsightWorkflowFile.model_validate(
                _workflow_payload(
                    souls={
                        "writer": {
                            "id": "writer",
                            "kind": "soul",
                            "role": "Inline Writer",
                            "system_prompt": "Draft carefully.",
                        }
                    }
                )
            )

        with pytest.raises(ValidationError):
            RunsightWorkflowFile.model_validate(
                _workflow_payload(
                    souls={
                        "writer": {
                            "id": "writer",
                            "name": "Inline Writer",
                            "role": "Inline Writer",
                            "system_prompt": "Draft carefully.",
                        }
                    }
                )
            )

    def test_inline_soul_parses_with_embedded_identity(self) -> None:
        wf = RunsightWorkflowFile.model_validate(
            _workflow_payload(
                souls={
                    "writer": {
                        "id": "writer",
                        "kind": "soul",
                        "name": "Inline Writer",
                        "role": "Inline Writer",
                        "system_prompt": "Draft carefully.",
                    }
                }
            )
        )

        assert wf.souls["writer"].id == "writer"
        assert wf.souls["writer"].kind == "soul"
        assert wf.souls["writer"].name == "Inline Writer"
