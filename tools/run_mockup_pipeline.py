#!/usr/bin/env python3
"""
Runsight Dogfooding: Mockup Pipeline Runner

Runs the mockup_pipeline workflow which:
1. Generates an HTML mockup via debate (UI Builder vs UX Reviewer)
2. Gates quality (PASS/FAIL with retry)
3. Writes the result to .agora/mockups/

Usage:
    python tools/run_mockup_pipeline.py [--screen SCREEN_NAME] [--model MODEL_NAME]

Examples:
    python tools/run_mockup_pipeline.py
    python tools/run_mockup_pipeline.py --screen canvas --model claude-haiku-4-5-20251001
    python tools/run_mockup_pipeline.py --screen dashboard --model gpt-4o-mini
"""

import argparse
import asyncio
import logging
import re
import sys
import time
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "libs" / "core" / "src"))

from runsight_core.observer import CompositeObserver, FileObserver, LoggingObserver  # noqa: E402
from runsight_core.primitives import Task  # noqa: E402
from runsight_core.state import WorkflowState  # noqa: E402
from runsight_core.yaml.parser import parse_workflow_yaml  # noqa: E402
from runsight_core.yaml.registry import WorkflowRegistry  # noqa: E402

SCREEN_DESCRIPTIONS = {
    "canvas": {
        "title": "Visual Workflow Canvas",
        "instruction": (
            "Generate a production-quality HTML mockup for the Visual Workflow Canvas screen "
            "of an AI agent workflow builder application.\n\n"
            "This is the PRIMARY screen of the application. It must include:\n"
            "- Left sidebar with navigation (Dashboard, Workflows, Agents, Runs, Settings)\n"
            "- Main canvas area with a node-based workflow editor\n"
            "- Block palette/toolbar for dragging new blocks onto the canvas\n"
            "- At least 4 connected workflow blocks on the canvas (e.g., LinearBlock -> DebateBlock -> GateBlock -> FileWriterBlock)\n"
            "- Block inspector panel on the right (shows config for selected block)\n"
            "- Top toolbar with workflow name, save/run buttons, zoom controls\n"
            "- Status bar at bottom with connection status and cost tracker\n\n"
            "Show ALL states as separate sections on the same scrollable page:\n"
            "1. Default state (workflow loaded, nothing selected)\n"
            "2. Block selected state (inspector panel populated)\n"
            "3. Workflow running state (blocks showing execution progress)\n"
            "4. Error state (a block failed, showing error details)\n"
            "5. Empty state (no workflow loaded, onboarding prompt)\n"
        ),
        "output_file": ".agora/mockups/canvas_screen.html",
    },
    "dashboard": {
        "title": "Dashboard Overview",
        "instruction": (
            "Generate a production-quality HTML mockup for the Dashboard screen "
            "of an AI agent workflow builder application.\n\n"
            "This screen shows an overview of all workflows, recent runs, and system status.\n"
            "Include: workflow cards with status badges, recent activity feed, "
            "cost summary chart, quick-action buttons, and empty state."
        ),
        "output_file": ".agora/mockups/dashboard_screen.html",
    },
}


def load_context() -> str:
    """Load component library and screen map as context string."""
    context_parts = []

    comp_lib = PROJECT_ROOT / ".agora" / "design" / "components" / "component_library.md"
    if comp_lib.exists():
        content = comp_lib.read_text(encoding="utf-8")
        # Truncate to keep token count reasonable
        if len(content) > 8000:
            content = content[:8000] + "\n\n... [truncated for token budget] ..."
        context_parts.append(f"=== COMPONENT LIBRARY ===\n{content}")

    screen_map = PROJECT_ROOT / ".agora" / "design" / "draft_screen_map.md"
    if screen_map.exists():
        content = screen_map.read_text(encoding="utf-8")
        if len(content) > 4000:
            content = content[:4000] + "\n\n... [truncated for token budget] ..."
        context_parts.append(f"=== SCREEN MAP ===\n{content}")

    if not context_parts:
        context_parts.append("No design context files found. Generate based on best practices.")

    return "\n\n".join(context_parts)


def patch_workflow_model(workflow_yaml_path: str, model_name: str) -> str:
    """Read workflow YAML and override the model_name in config."""
    content = Path(workflow_yaml_path).read_text(encoding="utf-8")
    # Simple string replacement for model override
    content = re.sub(
        r"model_name:\s*\S+",
        f"model_name: {model_name}",
        content,
    )
    return content


async def run_pipeline(screen_name: str, model_name: str) -> None:
    """Run the mockup pipeline for a given screen."""
    screen = SCREEN_DESCRIPTIONS.get(screen_name)
    if screen is None:
        print(f"Unknown screen: {screen_name}")
        print(f"Available: {', '.join(SCREEN_DESCRIPTIONS.keys())}")
        sys.exit(1)

    print(f"{'=' * 60}")
    print(f"Runsight Mockup Pipeline — {screen['title']}")
    print(f"Model: {model_name}")
    print(f"{'=' * 60}")

    # Step 1: Load context
    print("\n[1/4] Loading design context...")
    context = load_context()
    print(f"  Context loaded: {len(context)} chars")

    # Step 2: Build initial state
    print("\n[2/4] Building initial state...")
    task = Task(
        id=f"mockup_{screen_name}",
        instruction=screen["instruction"],
        context=context,
    )
    initial_state = WorkflowState(current_task=task)

    # Step 3: Load and parse workflow
    print("\n[3/4] Loading workflow pipeline...")
    registry = WorkflowRegistry()

    # Parse outer workflow (it references inner workflow via file path)
    outer_yaml_path = str(PROJECT_ROOT / "custom" / "workflows" / "mockup_pipeline.yaml")

    # Override model if specified
    if model_name != "claude-haiku-4-5-20251001":
        yaml_content = patch_workflow_model(outer_yaml_path, model_name)
        workflow = parse_workflow_yaml(yaml_content, workflow_registry=registry)
    else:
        workflow = parse_workflow_yaml(outer_yaml_path, workflow_registry=registry)

    print(f"  Workflow '{workflow.name}' loaded successfully")

    # Step 4: Run
    print("\n[4/4] Running pipeline...")
    start_time = time.time()

    # Set up monitoring
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )
    observer = CompositeObserver(
        LoggingObserver(),
        FileObserver(".agora/mockups/pipeline.log"),
    )

    try:
        final_state = await workflow.run(
            initial_state, workflow_registry=registry, observer=observer
        )
        elapsed = time.time() - start_time

        print(f"\n{'=' * 60}")
        print("PIPELINE COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Duration:    {elapsed:.1f}s")
        print(f"  Total cost:  ${final_state.total_cost_usd:.4f}")
        print(f"  Total tokens: {final_state.total_tokens:,}")
        print(f"  Output file: {screen['output_file']}")
        print(f"\n  Results keys: {list(final_state.results.keys())}")

        # Show block execution log
        print("\n  Execution log:")
        for msg in final_state.messages:
            if msg["role"] == "system":
                print(f"    {msg['content']}")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n{'=' * 60}")
        print(f"PIPELINE FAILED after {elapsed:.1f}s")
        print(f"{'=' * 60}")
        print(f"  Error: {type(e).__name__}: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Run Runsight mockup pipeline")
    parser.add_argument(
        "--screen",
        default="canvas",
        choices=list(SCREEN_DESCRIPTIONS.keys()),
        help="Screen to generate mockup for (default: canvas)",
    )
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="LLM model to use (default: claude-haiku-4-5-20251001)",
    )
    args = parser.parse_args()

    asyncio.run(run_pipeline(args.screen, args.model))


if __name__ == "__main__":
    main()
