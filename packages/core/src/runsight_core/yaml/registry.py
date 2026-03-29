"""
WorkflowRegistry: resolution registry for workflow references.

Maps workflow names/paths to loaded RunsightWorkflowFile instances.
Supports both exact name match and file path loading with normalization.
"""

from pathlib import Path
from typing import Dict

import yaml

from runsight_core.yaml.schema import RunsightWorkflowFile


class WorkflowRegistry:
    """
    Registry for resolving workflow_ref strings to RunsightWorkflowFile instances.

    Resolution order:
    1. Exact name match in _registry dict
    2. Treat ref as relative file path:
       - Normalize using Path.resolve()
       - Load YAML from disk
       - Parse using RunsightWorkflowFile.model_validate()
       - Cache under normalized path
    3. Raise ValueError with available keys if unresolvable

    Usage:
        registry = WorkflowRegistry()

        # Pre-register workflows by name
        registry.register("analysis", analysis_workflow_file)

        # Resolve by name
        wf_file = registry.get("analysis")  # → returns analysis_workflow_file

        # Resolve by file path (loads from disk, caches result)
        wf_file = registry.get("./workflows/analysis.yaml")
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._registry: Dict[str, RunsightWorkflowFile] = {}

    def register(self, name: str, workflow_file: RunsightWorkflowFile) -> None:
        """
        Register a workflow under a given name.

        Args:
            name: Key for lookup (exact string match).
            workflow_file: Parsed RunsightWorkflowFile instance.

        Note: Silently overwrites if name already registered.
        """
        self._registry[name] = workflow_file

    def get(self, ref: str) -> RunsightWorkflowFile:
        """
        Resolve workflow reference to RunsightWorkflowFile instance.

        Resolution algorithm:
        1. Check _registry for exact name match → return immediately if found
        2. Treat ref as file path:
           a. Normalize path using pathlib.Path(ref).resolve()
           b. Convert normalized path to string
           c. Check _registry for cached normalized path → return if found
           d. If not cached:
              - Open file, load YAML
              - Validate using RunsightWorkflowFile.model_validate()
              - Cache in _registry under normalized path string
              - Return workflow_file
        3. If neither name match nor file load succeeds → raise ValueError

        Args:
            ref: Workflow name (e.g., "analysis_pipeline") or relative file path
                 (e.g., "./workflows/analysis.yaml", "../shared/workflow.yaml").

        Returns:
            Loaded and validated RunsightWorkflowFile instance.

        Raises:
            ValueError: If ref is not a registered name and not a valid file path.
                       Error message includes list of available registered names.
            FileNotFoundError: If ref is treated as file path but file does not exist.
            yaml.YAMLError: If file content is syntactically invalid YAML.
            pydantic.ValidationError: If YAML structure doesn't match schema.
        """
        # Step 1: Exact name match
        if ref in self._registry:
            return self._registry[ref]

        # Step 2: Treat as file path
        try:
            # Normalize path (resolves relative paths, follows symlinks)
            normalized_path = Path(ref).resolve()
            normalized_str = str(normalized_path)

            # Check cache for normalized path
            if normalized_str in self._registry:
                return self._registry[normalized_str]

            # Load from disk
            with open(normalized_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)

            # Validate schema
            workflow_file = RunsightWorkflowFile.model_validate(raw_data)

            # Cache under normalized path
            self._registry[normalized_str] = workflow_file

            return workflow_file

        except (FileNotFoundError, OSError) as e:
            # File path resolution failed
            available_keys = sorted(self._registry.keys())
            raise ValueError(
                f"WorkflowRegistry: cannot resolve ref '{ref}'. "
                f"Not found as registered name, and file loading failed: {e}. "
                f"Available registered names: {available_keys}"
            )
