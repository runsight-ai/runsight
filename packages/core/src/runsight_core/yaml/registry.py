"""
WorkflowRegistry: resolution registry for workflow references.

Maps workflow ids to loaded RunsightWorkflowFile instances.
"""

from typing import Dict

from runsight_core.yaml.schema import RunsightWorkflowFile


class WorkflowRegistry:
    """
    Registry for resolving workflow_ref strings to RunsightWorkflowFile instances.

    Resolution order:
    1. Exact registered workflow id match in _registry dict
    2. Raise ValueError with available ids if unresolvable

    Usage:
        registry = WorkflowRegistry()

        # Pre-register workflows by embedded workflow id
        registry.register("analysis", analysis_workflow_file)

        # Resolve by id
        wf_file = registry.get("analysis")  # → returns analysis_workflow_file
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
        1. Check _registry for exact workflow id match → return immediately if found
        2. Otherwise raise ValueError with available registered ids

        Args:
            ref: Embedded workflow id (e.g., "analysis_pipeline").

        Returns:
            Loaded and validated RunsightWorkflowFile instance.

        Raises:
            ValueError: If ref is not a registered workflow id.
        """
        if ref in self._registry:
            return self._registry[ref]

        available_keys = sorted(self._registry.keys())
        raise ValueError(
            f"WorkflowRegistry: cannot resolve ref '{ref}'. "
            f"Not found among registered workflow ids. Available registered ids: {available_keys}"
        )
