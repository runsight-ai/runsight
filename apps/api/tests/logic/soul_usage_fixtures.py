"""Workflow YAML snippets for soul usage scanning tests."""

from __future__ import annotations

BROKEN_SOULS_YAML = "souls: [broken"
MALFORMED_BLOCKS_YAML = "blocks: [broken yaml {{{"


def linear_blocks_yaml(
    *soul_refs: str,
    block_names: tuple[str, ...] | None = None,
    include_unreferenced_block: bool = False,
) -> str:
    names = block_names or tuple(f"step{index}" for index, _ in enumerate(soul_refs, start=1))
    lines = ["blocks:"]
    for name, soul_ref in zip(names, soul_refs, strict=True):
        lines.extend(
            [
                f"  {name}:",
                "    type: linear",
                f"    soul_ref: {soul_ref}",
            ]
        )
    if include_unreferenced_block:
        lines.extend(
            [
                "  ignored:",
                "    type: linear",
            ]
        )
    return "\n".join(lines) + "\n"


def linear_block_without_soul_ref_yaml(block_name: str = "step") -> str:
    return "\n".join(["blocks:", f"  {block_name}:", "    type: linear"]) + "\n"


def dispatch_exit_yaml(
    soul_ref: str,
    *,
    block_name: str = "route",
    exit_id: str = "research_exit",
    label: str | None = "Research",
    task: str | None = "Do research",
) -> str:
    lines = [
        "blocks:",
        f"  {block_name}:",
        "    type: dispatch",
        "    exits:",
        f"      - id: {exit_id}",
    ]
    if label is not None:
        lines.append(f"        label: {label}")
    lines.append(f"        soul_ref: {soul_ref}")
    if task is not None:
        lines.append(f"        task: {task}")
    return "\n".join(lines) + "\n"


def linear_and_dispatch_exit_yaml(
    linear_ref: str,
    dispatch_ref: str,
    *,
    linear_block_name: str = "step1",
    dispatch_block_name: str = "step2",
) -> str:
    return (
        "blocks:\n"
        f"  {linear_block_name}:\n"
        "    type: linear\n"
        f"    soul_ref: {linear_ref}\n"
        f"  {dispatch_block_name}:\n"
        "    type: dispatch\n"
        "    exits:\n"
        "      - id: e1\n"
        f"        soul_ref: {dispatch_ref}\n"
    )


def legacy_soul_section_yaml(
    declared_soul_id: str,
    block_ref: str,
    *,
    declared_role: str = "Legacy",
    system_prompt: str | None = "I am legacy",
    block_name: str = "draft",
) -> str:
    lines = [
        "souls:",
        f"  {declared_soul_id}:",
        f"    role: {declared_role}",
    ]
    if system_prompt is not None:
        lines.append(f"    system_prompt: {system_prompt}")
    lines.extend(
        [
            "blocks:",
            f"  {block_name}:",
            "    type: linear",
            f"    soul_ref: {block_ref}",
        ]
    )
    return "\n".join(lines) + "\n"


def legacy_soul_id_section_yaml(
    declared_soul_id: str,
    block_ref: str,
    *,
    block_name: str = "review",
) -> str:
    return (
        "souls:\n"
        f"  {declared_soul_id}:\n"
        f"    id: {declared_soul_id}\n"
        "blocks:\n"
        f"  {block_name}:\n"
        "    type: linear\n"
        f"    soul_ref: {block_ref}\n"
    )


def no_blocks_yaml(*, name: str = "Empty Workflow", description: str | None = None) -> str:
    lines = ["workflow:", f"  name: {name}"]
    if description is not None:
        lines.append(f"  description: {description}")
    return "\n".join(lines) + "\n"


def wrong_shape_blocks_yaml(soul_ref: str) -> str:
    return "\n".join(["blocks:", f"  - soul_ref: {soul_ref}"]) + "\n"
