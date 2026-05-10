"""IsolatedBlockWrapper — wraps LLM blocks for workspace harness execution."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urlparse

from runsight_core.blocks.base import BaseBlock
from runsight_core.budget_enforcement import budget_killed_exception_from_message
from runsight_core.context_governance import (
    ContextReadDeniedError,
    ContextResolver,
    collect_context_declaration,
    suppress_declared_inputs_for_block,
)
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    PromptEnvelope,
    ResultEnvelope,
    SoulEnvelope,
    ToolDefEnvelope,
)
from runsight_core.isolation.errors import BlockExecutionError
from runsight_core.isolation.workspace import (
    HostToolExecutionRef,
    HostToolExecutionRegistry,
    WorkerToolRegistry,
    WorkspaceHostBindings,
    WorkspaceManifest,
    WorkspacePolicy,
    WorkspaceRunRequest,
)
from runsight_core.state import BlockResult

if TYPE_CHECKING:
    from runsight_core.block_io import BlockContext, BlockOutput

# Block types whose soul attribute is not named "soul"
_SOUL_ATTR_MAP = {
    "GateBlock": "gate_soul",
    "SynthesizeBlock": "synthesizer_soul",
}

# LLM block types that should be wrapped at build time
LLM_BLOCK_TYPES = frozenset({"linear", "gate", "synthesize", "dispatch"})
_HTTP_URL_ALLOWLIST_ENV = "RUNSIGHT_HTTP_URL_ALLOWLIST"
_HTTP_ALLOWLIST_SPLIT = re.compile(r"[\s,]+")


_BLOCK_TYPE_MAP = {
    "LinearBlock": "linear",
    "GateBlock": "gate",
    "SynthesizeBlock": "synthesize",
    "DispatchBlock": "dispatch",
}


def _get_soul(inner_block: BaseBlock) -> Any:
    """Extract the soul from an inner block, handling different attribute names."""
    if type(inner_block).__name__ == "DispatchBlock":
        branches = getattr(inner_block, "branches", [])
        if branches:
            return getattr(branches[0], "soul", None)
    attr_name = _SOUL_ATTR_MAP.get(type(inner_block).__name__, "soul")
    return getattr(inner_block, attr_name, None)


def _collect_resolved_tools(inner_block: BaseBlock, soul: Any) -> list[Any]:
    if type(inner_block).__name__ == "DispatchBlock":
        tools_by_name: dict[str, Any] = {}
        for branch in getattr(inner_block, "branches", []):
            branch_soul = getattr(branch, "soul", None)
            branch_tool_names: set[str] = set()
            for tool in getattr(branch_soul, "resolved_tools", None) or []:
                tool_name = str(tool.name)
                if tool_name in branch_tool_names:
                    raise ValueError(f"duplicate tool name in dispatch branch: {tool_name}")
                branch_tool_names.add(tool_name)
                tools_by_name.setdefault(tool_name, tool)
        return list(tools_by_name.values())
    return list(getattr(soul, "resolved_tools", None) or [])


def _build_tool_envelopes_from_tools(resolved_tools: list[Any]) -> list[ToolDefEnvelope]:
    """Serialize resolved tool metadata for the worker-side tool loop."""
    tool_envelopes: list[ToolDefEnvelope] = []

    for tool in resolved_tools:
        exits = []
        port_enum = (
            getattr(tool, "parameters", {}).get("properties", {}).get("port", {}).get("enum", [])
        )
        if isinstance(port_enum, list):
            exits = [str(port) for port in port_enum]

        tool_envelopes.append(
            ToolDefEnvelope(
                source=str(getattr(tool, "source", "") or tool.name),
                config=dict(getattr(tool, "config", {}) or {}),
                exits=exits,
                name=tool.name,
                description=tool.description,
                parameters=dict(tool.parameters or {}),
                tool_type=str(getattr(tool, "tool_type", "")),
            )
        )

    return tool_envelopes


def _build_tool_envelopes(soul: Any) -> list[ToolDefEnvelope]:
    return _build_tool_envelopes_from_tools(list(getattr(soul, "resolved_tools", None) or []))


def _serialize_scoped_results(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize workflow results for the isolation envelope.

    WorkflowBlock output mappings may write plain strings/dicts back into
    ``state.results`` instead of BlockResult instances. The isolation envelope
    still needs a uniform object shape for worker-side reconstruction.
    """
    serialized: dict[str, dict[str, Any]] = {}
    for key, value in results.items():
        if isinstance(value, BlockResult):
            serialized[key] = value.model_dump()
        else:
            serialized[key] = {"output": value}
    return serialized


def _scoped_context_for_envelope(
    block: BaseBlock,
    state: Any,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    str,
    list[Any],
]:
    access = str(getattr(block, "context_access", "declared"))
    if access != "declared":
        raise ContextReadDeniedError(
            f"Context access '{access}' is not implemented for {block.block_id}"
        )
    if state is None:
        return {}, {}, {}, {}, {}, access, []

    declaration = collect_context_declaration(block)
    resolver = ContextResolver(
        run_id=str(state.metadata.get("run_id", "")),
        workflow_name=str(state.metadata.get("workflow_name", "")),
    )
    scoped = resolver.resolve(declaration=declaration, state=state)
    return (
        dict(scoped.inputs),
        dict(scoped.scoped_workflow_inputs),
        _serialize_scoped_results(scoped.scoped_results),
        dict(scoped.scoped_shared_memory),
        dict(scoped.scoped_metadata),
        access,
        [scoped.audit_event],
    )


def _serialize_soul_summary(soul: Any) -> dict[str, Any]:
    return {
        "id": getattr(soul, "id", ""),
        "role": getattr(soul, "role", ""),
        "system_prompt": getattr(soul, "system_prompt", ""),
        "model_name": getattr(soul, "model_name", ""),
        "provider": getattr(soul, "provider", "") or "",
        "temperature": getattr(soul, "temperature", None),
        "max_tokens": getattr(soul, "max_tokens", None),
        "required_tool_calls": list(getattr(soul, "required_tool_calls", None) or []),
        "max_tool_iterations": getattr(soul, "max_tool_iterations", 5),
    }


def _build_block_metadata(inner_block: BaseBlock) -> tuple[str, dict[str, Any]]:
    block_class_name = type(inner_block).__name__
    block_type = _BLOCK_TYPE_MAP.get(
        block_class_name, block_class_name.removesuffix("Block").lower()
    )
    block_config: dict[str, Any] = {}
    limits = getattr(inner_block, "limits", None)
    if limits is not None:
        block_config["limits"] = (
            limits.model_dump(exclude_none=True) if hasattr(limits, "model_dump") else limits
        )

    if block_type == "gate":
        block_config.update(
            {
                "eval_key": getattr(inner_block, "eval_key", ""),
                "extract_field": getattr(inner_block, "extract_field", None),
            }
        )
    elif block_type == "synthesize":
        block_config.update(
            {
                "input_block_ids": list(getattr(inner_block, "input_block_ids", [])),
                "synthesizer_soul": _serialize_soul_summary(
                    getattr(inner_block, "synthesizer_soul", None)
                ),
            }
        )
    elif block_type == "dispatch" and hasattr(inner_block, "branches"):
        block_config["branches"] = [
            {
                "exit_id": branch.exit_id,
                "label": branch.label,
                "task_instruction": branch.task_instruction,
                "soul": _serialize_soul_summary(branch.soul),
            }
            for branch in inner_block.branches
        ]

    return block_type, block_config


def _workspace_policy() -> WorkspacePolicy:
    return WorkspacePolicy(
        network={"raw": "deny", "mediated": "allow"},
        filesystem={"raw": "deny", "mediated": "workspace"},
        credentials={"mode": "host-bound"},
    )


def _build_host_tool_registry(resolved_tools: list[Any]) -> HostToolExecutionRegistry:
    return HostToolExecutionRegistry(
        tools=[
            HostToolExecutionRef(
                name=tool.name,
                tool=tool,
                credential_refs=list(getattr(tool, "credential_refs", None) or []),
                headers=dict(getattr(tool, "headers", None) or {}),
                secret_config=dict(getattr(tool, "secret_config", None) or {}),
                host_path=getattr(tool, "host_path", None),
                policy_metadata=dict(getattr(tool, "policy_metadata", None) or {}),
                source=getattr(tool, "source", None),
                tool_type=getattr(tool, "tool_type", None),
                config=dict(getattr(tool, "config", None) or {}),
                request_config=getattr(tool, "request_config", None),
                timeout_seconds=getattr(tool, "timeout_seconds", None),
                max_output_bytes=getattr(tool, "max_output_bytes", None),
                response_size_policy=getattr(tool, "response_size_policy", None),
            )
            for tool in resolved_tools
        ]
    )


def _hostname_from_allowlist_entry(value: str) -> str | None:
    entry = value.strip()
    if not entry:
        return None
    parsed = urlparse(entry)
    if parsed.hostname is not None:
        hostname = parsed.hostname
    elif "://" in entry:
        hostname = ""
    else:
        host_part = entry.split("/", 1)[0].rsplit("@", 1)[-1]
        raw_hostname, separator, raw_port = host_part.rpartition(":")
        if separator:
            hostname = raw_hostname if raw_hostname and raw_port.isdigit() else ""
        else:
            hostname = host_part
    hostname = hostname.strip().lower()
    return hostname or None


def _static_request_hostname(request_config: dict[str, Any] | None) -> str | None:
    if not request_config:
        return None
    raw_url = str(request_config.get("url") or "")
    parsed = urlparse(raw_url)
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname or any(marker in hostname for marker in ("{", "}", "$")):
        return None
    return hostname


def _http_url_allowlist_from_host_tools(
    host_tools: HostToolExecutionRegistry,
) -> list[str]:
    hosts = {
        hostname
        for ref in host_tools.tools
        if (hostname := _static_request_hostname(ref.request_config)) is not None
    }
    return sorted(hosts)


def _http_url_allowlist_from_env() -> list[str]:
    raw_allowlist = os.environ.get(_HTTP_URL_ALLOWLIST_ENV, "")
    hosts = {
        hostname
        for entry in _HTTP_ALLOWLIST_SPLIT.split(raw_allowlist)
        if (hostname := _hostname_from_allowlist_entry(entry)) is not None
    }
    return sorted(hosts)


def _build_workspace_host_bindings(
    *,
    api_keys: dict[str, str],
    host_tools: HostToolExecutionRegistry,
) -> WorkspaceHostBindings:
    return WorkspaceHostBindings(
        api_keys=dict(api_keys),
        host_tools=host_tools,
        url_allowlist=sorted(
            {
                *_http_url_allowlist_from_host_tools(host_tools),
                *_http_url_allowlist_from_env(),
            }
        ),
    )


class IsolatedBlockWrapper(BaseBlock):
    """Wraps an LLM block to execute it through the workspace isolation harness.

    Delegates execution to ``_run_in_subprocess`` with a WorkspaceRunRequest and
    maps the returned ResultEnvelope back onto WorkflowState.
    """

    def __init__(
        self,
        block_id: str,
        inner_block: BaseBlock,
        *,
        harness: Any | None = None,
        harness_factory: Callable[[], Any] | None = None,
        retry_config: Optional[Any] = None,
        api_keys: dict[str, str] | None = None,
    ):
        super().__init__(block_id, retry_config=retry_config)
        self.inner_block = inner_block
        self.soul = _get_soul(inner_block)
        self.harness = harness
        self._harness_factory = harness_factory
        self._api_keys = dict(api_keys or {})

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the inner block for attributes not on the wrapper."""
        return getattr(self.inner_block, name)

    async def _run_in_subprocess(self, request: WorkspaceRunRequest) -> ResultEnvelope:
        """Run the inner block through the configured workspace harness."""
        if self.harness is None:
            if self._harness_factory is None:
                raise NotImplementedError(
                    "Workspace harness is not configured on IsolatedBlockWrapper"
                )
            self.harness = self._harness_factory()
        return await self.harness.run(request)

    async def execute(self, ctx: "BlockContext") -> "BlockOutput":
        """Execute the inner block through the workspace isolation boundary.

        Builds a WorkspaceRunRequest and maps the ResultEnvelope back to
        BlockOutput.
        """
        from runsight_core.block_io import BlockOutput

        state = ctx.state_snapshot  # may be None if called from workflow dispatch

        # Build the context envelope
        soul = self.soul
        soul_envelope = SoulEnvelope(
            id=soul.id if soul else "",
            role=soul.role if soul else "",
            name=soul.name if soul else None,
            system_prompt=soul.system_prompt if soul else "",
            model_name=soul.model_name or "" if soul else "",
            provider=soul.provider or "" if soul else "",
            temperature=soul.temperature if soul else None,
            max_tokens=soul.max_tokens if soul else None,
            required_tool_calls=list(soul.required_tool_calls or []) if soul else [],
            max_tool_iterations=soul.max_tool_iterations
            if soul and hasattr(soul, "max_tool_iterations")
            else 5,
        )

        # Build prompt envelope from BlockContext
        raw_context = ctx.context
        prompt_context: dict = {"text": raw_context} if isinstance(raw_context, str) else {}
        task_envelope = PromptEnvelope(
            id=f"{self.block_id}_task",
            instruction=ctx.instruction or "",
            context=prompt_context,
        )

        # Gather conversation history for stateful blocks
        history_key = f"{self.block_id}_{soul.id}" if soul else self.block_id
        conversation_history = list(ctx.conversation_history) if self.inner_block.stateful else []

        (
            scoped_inputs,
            scoped_workflow_inputs,
            scoped_results,
            scoped_shared_memory,
            scoped_metadata,
            access,
            context_audit,
        ) = _scoped_context_for_envelope(self, state)
        envelope_inputs = dict(ctx.inputs) if state is None else scoped_inputs

        block_type, block_config = _build_block_metadata(self.inner_block)
        resolved_tools = _collect_resolved_tools(self.inner_block, soul)
        host_tools = _build_host_tool_registry(resolved_tools)
        worker_tools = WorkerToolRegistry.from_host_registry(host_tools).tools

        envelope = ContextEnvelope(
            block_id=self.block_id,
            block_type=block_type,
            block_config=block_config,
            soul=soul_envelope,
            tools=_build_tool_envelopes_from_tools(resolved_tools),
            prompt=task_envelope,
            inputs=envelope_inputs,
            scoped_workflow_inputs=dict(scoped_workflow_inputs),
            scoped_results=scoped_results,
            scoped_shared_memory=scoped_shared_memory,
            scoped_metadata=scoped_metadata,
            access=access,
            context_audit=context_audit,
            conversation_history=conversation_history,
            timeout_seconds=300,
            max_output_bytes=1_000_000,
        )
        request = WorkspaceRunRequest(
            envelope=envelope,
            manifest=WorkspaceManifest(materializations=[], working_dir="."),
            policy=_workspace_policy(),
            worker_tools=worker_tools,
            host_bindings=_build_workspace_host_bindings(
                api_keys=self._api_keys,
                host_tools=host_tools,
            ),
        )

        with suppress_declared_inputs_for_block(self.inner_block.block_id):
            result = await self._run_in_subprocess(request)

        # Handle errors from the workspace harness
        if result.error is not None:
            error_type = result.error_type or "BlockExecutionError"
            if error_type == "BudgetKilledException":
                budget_exc = budget_killed_exception_from_message(result.error)
                if budget_exc is not None:
                    raise budget_exc
            if error_type == "ValueError":
                raise ValueError(result.error)
            if error_type == "SubprocessError":
                raise BlockExecutionError(result.error, original_error_type=error_type)
            raise BlockExecutionError(result.error, original_error_type=error_type)

        # Build per-port extra results for dispatch blocks
        extra_results: dict | None = None
        if result.delegate_artifacts:
            extra_results = {
                f"{self.block_id}.{port}": BlockResult(
                    output=artifact.prompt,
                    exit_handle=port,
                )
                for port, artifact in result.delegate_artifacts.items()
            }

        # The worker returns the full stateful history, so replace instead of
        # appending to avoid duplicating prior turns on repeated isolated calls.
        conversation_replacements: dict | None = None
        if self.inner_block.stateful and result.conversation_history:
            conversation_replacements = {history_key: result.conversation_history}

        return BlockOutput(
            output=result.output or "",
            exit_handle=result.exit_handle,
            cost_usd=result.cost_usd,
            total_tokens=result.total_tokens,
            conversation_replacements=conversation_replacements,
            extra_results=extra_results,
        )
