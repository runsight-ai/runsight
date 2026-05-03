"""Fixture data for filesystem repository tests."""

import json
from pathlib import Path

import yaml

ORPHAN_CANVAS_STATE = {
    "nodes": [],
    "edges": [],
    "viewport": {"x": 0.0, "y": 0.0, "zoom": 1.0},
    "selected_node_id": None,
    "canvas_mode": "dag",
}

ORPHAN_STATE_MACHINE_CANVAS_STATE = {
    **ORPHAN_CANVAS_STATE,
    "selected_node_id": "orphan-canvas-selected-node",
    "canvas_mode": "state-machine",
}


def workflow_yaml(wf_id: str, name: str) -> str:
    return (
        f"id: {wf_id}\n"
        "kind: workflow\n"
        "version: '1.0'\n"
        "blocks: {}\n"
        "workflow:\n"
        f"  name: {name}\n"
        "  entry: start\n"
        "  transitions: []\n"
    )


def workflow_yaml_without_kind(wf_id: str, name: str) -> str:
    return (
        f"id: {wf_id}\n"
        "version: '1.0'\n"
        "blocks: {}\n"
        "workflow:\n"
        f"  name: {name}\n"
        "  entry: start\n"
        "  transitions: []\n"
    )


def hand_authored_workflow_payload() -> dict:
    return {
        "id": "my-hand-authored",
        "kind": "workflow",
        "version": "1.0",
        "blocks": {},
        "workflow": {
            "name": "Hand Authored",
            "entry": "start",
            "transitions": [],
        },
    }


def write_hand_authored_workflow(path: Path) -> None:
    path.write_text(yaml.dump(hand_authored_workflow_payload()))


def write_orphan_canvas_sidecar(path: Path, *, state: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state or ORPHAN_CANVAS_STATE))


def soul_payload(*, name: str) -> dict:
    return {"id": "sl-one", "kind": "soul", "name": name, "role": name}
