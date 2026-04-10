"""Helpers for custom assertion plugin adapters."""

from __future__ import annotations

import ast
import asyncio
import json
import os
import sys
import threading
from typing import Any, Callable

from runsight_core.assertions.base import AssertionContext, GradingResult
from runsight_core.assertions.contract import ASSERTION_FUNCTION_NAME, ASSERTION_FUNCTION_PARAMS
from runsight_core.blocks.code import BLOCKED_BUILTINS, BLOCKED_MODULES, DEFAULT_ALLOWED_IMPORTS


def _custom_assertion_type(plugin_name: str) -> str:
    return f"custom:{plugin_name}"


def _validate_bool_return(raw: Any, plugin_name: str) -> GradingResult:
    if type(raw) is not bool:
        raise TypeError(
            f"Custom assertion {plugin_name!r} declares returns: bool but get_assert returned "
            f"{type(raw).__name__!r}"
        )

    return GradingResult(
        passed=raw,
        score=1.0 if raw else 0.0,
        reason=f"Custom assertion {plugin_name!r} returned {raw}",
        assertion_type=_custom_assertion_type(plugin_name),
    )


def _validate_grading_result_return(raw: Any, plugin_name: str) -> GradingResult:
    if not isinstance(raw, dict):
        raise TypeError(
            f"Custom assertion {plugin_name!r} declares returns: grading_result but get_assert "
            f"returned {type(raw).__name__!r}; expected dict"
        )

    pass_key = next((key for key in ("passed", "pass_", "pass") if key in raw), None)
    if pass_key is None or "score" not in raw:
        actual_keys = sorted(raw.keys())
        raise TypeError(
            f"Custom assertion {plugin_name!r} grading_result must provide keys "
            f"['passed'|'pass_'|'pass', 'score']; actual keys: {actual_keys}"
        )

    passed = raw[pass_key]
    if type(passed) is not bool:
        raise TypeError(
            f"Custom assertion {plugin_name!r} grading_result field {pass_key!r} must be bool"
        )

    score = raw["score"]
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise TypeError(
            f"Custom assertion {plugin_name!r} grading_result field 'score' must be numeric"
        )
    score = float(score)
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"Custom assertion {plugin_name!r}: score must be between 0.0 and 1.0")

    reason = raw.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)

    return GradingResult(
        passed=passed,
        score=score,
        reason=reason,
        assertion_type=_custom_assertion_type(plugin_name),
    )


_RETURN_VALIDATORS: dict[str, Callable[[Any, str], GradingResult]] = {
    "bool": _validate_bool_return,
    "grading_result": _validate_grading_result_return,
}

_DEFAULT_PLUGIN_TIMEOUT_SECONDS = 30


def _assertion_signature() -> str:
    params = ", ".join(ASSERTION_FUNCTION_PARAMS)
    return f"def {ASSERTION_FUNCTION_NAME}({params})"


def _validate_adapter_code(code: str) -> None:
    """Validate custom assertion code before execution."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Custom assertion code has a syntax error: {exc}") from exc

    has_get_assert = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in BLOCKED_MODULES:
                    raise ValueError(f"Import of '{alias.name}' is not allowed")
                if top not in DEFAULT_ALLOWED_IMPORTS:
                    raise ValueError(f"Import of '{alias.name}' is not in the allowed list")

        if isinstance(node, ast.ImportFrom) and node.module is not None:
            top = node.module.split(".")[0]
            if top in BLOCKED_MODULES:
                raise ValueError(f"Import from '{node.module}' is not allowed")
            if top not in DEFAULT_ALLOWED_IMPORTS:
                raise ValueError(f"Import from '{node.module}' is not in the allowed list")

        if isinstance(node, ast.Call):
            func = node.func
            name: str | None = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name and name in BLOCKED_BUILTINS:
                raise ValueError(f"Call to '{name}()' is not allowed")

        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("__") and attr.endswith("__"):
                raise ValueError(f"Access to dunder attribute '{attr}' is not allowed")

        if isinstance(node, ast.AsyncFunctionDef) and node.name == ASSERTION_FUNCTION_NAME:
            raise ValueError(f"Custom assertion code must define '{_assertion_signature()}'")

        if isinstance(node, ast.FunctionDef) and node.name == ASSERTION_FUNCTION_NAME:
            has_get_assert = True
            if (
                len(node.args.posonlyargs) != 0
                or len(node.args.args) != len(ASSERTION_FUNCTION_PARAMS)
                or tuple(arg.arg for arg in node.args.args) != ASSERTION_FUNCTION_PARAMS
                or node.args.vararg is not None
                or len(node.args.kwonlyargs) != 0
                or node.args.kwarg is not None
            ):
                raise ValueError(f"Custom assertion code must define '{_assertion_signature()}'")

    if not has_get_assert:
        raise ValueError(f"Custom assertion code must define '{_assertion_signature()}'")


def _adapter_harness(code: str) -> str:
    return (
        "import json\n\n"
        + code
        + "\n\n"
        + "_input = json.loads(open(0).read())\n"
        + f"_result = {ASSERTION_FUNCTION_NAME}(_input['output'], _input['context'])\n"
        + "print(json.dumps(_result), end='')\n"
    )


def _build_plugin_context(
    config: dict[str, Any] | None, context: AssertionContext
) -> dict[str, Any]:
    return {
        "vars": context.variables,
        "config": config,
        "prompt": context.prompt,
        "prompt_hash": context.prompt_hash,
        "soul_id": context.soul_id,
        "soul_version": context.soul_version,
        "block_id": context.block_id,
        "block_type": context.block_type,
        "cost_usd": context.cost_usd,
        "total_tokens": context.total_tokens,
        "latency_ms": context.latency_ms,
        "run_id": context.run_id,
        "workflow_id": context.workflow_id,
    }


def _minimal_subprocess_env() -> dict[str, str]:
    minimal_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")}
    for key in ("HOME", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
        if key in os.environ:
            minimal_env[key] = os.environ[key]
    return minimal_env


async def _run_plugin(
    harness: str,
    output: str,
    plugin_context: dict[str, Any],
    *,
    timeout_seconds: int = _DEFAULT_PLUGIN_TIMEOUT_SECONDS,
) -> Any:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        harness,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_minimal_subprocess_env(),
    )

    stdin_data = json.dumps({"output": output, "context": plugin_context}).encode()
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=stdin_data),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        try:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass
        raise TimeoutError(f"custom assertion plugin timed out after {timeout_seconds}s") from exc

    if proc.returncode != 0:
        error_msg = stderr_bytes.decode(errors="replace").strip() or "plugin subprocess failed"
        raise RuntimeError(error_msg)

    stdout = stdout_bytes.decode(errors="replace").strip()
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"plugin returned invalid JSON: {stdout!r}") from exc


def _run_plugin_sync(
    harness: str,
    output: str,
    plugin_context: dict[str, Any],
    *,
    timeout_seconds: int = _DEFAULT_PLUGIN_TIMEOUT_SECONDS,
) -> Any:
    coroutine = _run_plugin(
        harness,
        output,
        plugin_context,
        timeout_seconds=timeout_seconds,
    )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result: Any | None = None
    error: BaseException | None = None

    def _runner() -> None:
        nonlocal result, error
        try:
            result = asyncio.run(coroutine)
        except BaseException as exc:  # pragma: no cover - surfaced to caller
            error = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if error is not None:
        raise error
    return result


def _build_adapter_class(plugin_name: str, code: str, returns: str) -> type:
    """Build a synchronous assertion adapter class for a custom plugin."""
    _validate_adapter_code(code)
    harness = _adapter_harness(code)
    assertion_type = _custom_assertion_type(plugin_name)

    if returns not in _RETURN_VALIDATORS:
        raise ValueError(f"Unsupported custom assertion return contract: {returns!r}")

    validator = _RETURN_VALIDATORS[returns]

    class CustomAssertionAdapter:
        type = assertion_type

        def __init__(
            self,
            value: Any = None,
            threshold: float | None = None,
            config: dict[str, Any] | None = None,
        ) -> None:
            self.value = value
            self.threshold = threshold
            self.config = config

        def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
            plugin_context = _build_plugin_context(self.config, context)
            try:
                raw = _run_plugin_sync(harness, output, plugin_context)
                return validator(raw, plugin_name)
            except Exception as exc:
                return GradingResult(
                    passed=False,
                    score=0.0,
                    reason=f"Custom assertion {plugin_name!r} failed: {exc}",
                    assertion_type=assertion_type,
                )

    CustomAssertionAdapter.__name__ = f"{plugin_name.title().replace('_', '')}AssertionAdapter"
    return CustomAssertionAdapter
