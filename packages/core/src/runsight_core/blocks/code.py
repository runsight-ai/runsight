"""
CodeBlock — sandboxed Python code execution.

Co-located: runtime class + BlockDef schema + build() function.
"""

import ast
import asyncio
import json
import sys
import textwrap
from typing import Any, Dict, List, Literal, Optional

from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ALLOWED_IMPORTS: List[str] = [
    "json",
    "re",
    "math",
    "datetime",
    "collections",
    "itertools",
    "hashlib",
    "base64",
    "time",
    "urllib.parse",
]

BLOCKED_BUILTINS: set = {
    "__import__",
    "open",
    "exec",
    "eval",
    "compile",
    "globals",
    "locals",
    "breakpoint",
    "getattr",
    "setattr",
    "delattr",
    "type",
    "vars",
    "dir",
}

BLOCKED_MODULES: set = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "importlib",
    "builtins",
    "types",
    "ctypes",
    "code",
    "_thread",
}


def _validate_code_ast(code: str, allowed_imports: List[str]) -> None:
    """
    Parse *code* with :func:`ast.parse` and reject dangerous constructs.

    Raises:
        ValueError: If the code contains forbidden imports, builtins, or
            is missing a ``def main(data)`` function.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Code has a syntax error: {exc}") from exc

    has_main = False

    for node in ast.walk(tree):
        # --- import <module> ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in BLOCKED_MODULES:
                    raise ValueError(f"Import of '{alias.name}' is not allowed")
                if top not in allowed_imports:
                    raise ValueError(f"Import of '{alias.name}' is not in the allowed list")

        # --- from <module> import ... ---
        if isinstance(node, ast.ImportFrom):
            if node.module is not None:
                top = node.module.split(".")[0]
                if top in BLOCKED_MODULES:
                    raise ValueError(f"Import from '{node.module}' is not allowed")
                if top not in allowed_imports:
                    raise ValueError(f"Import from '{node.module}' is not in the allowed list")

        # --- function calls: __import__, open, eval, exec, compile, etc. ---
        if isinstance(node, ast.Call):
            func = node.func
            name: Optional[str] = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name and name in BLOCKED_BUILTINS:
                raise ValueError(f"Call to '{name}()' is not allowed")

        # --- dunder attribute access: obj.__class__, obj.__globals__, etc. ---
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("__") and attr.endswith("__"):
                raise ValueError(f"Access to dunder attribute '{attr}' is not allowed")

        # --- detect def main ---
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            has_main = True

    if not has_main:
        raise ValueError("Code must define a 'def main(data)' function")


_HARNESS_PREFIX = textwrap.dedent(
    """\
import json

"""
)

_HARNESS_SUFFIX = textwrap.dedent(
    """

# --- harness ---
_input = json.loads(open(0).read())
_result = main(_input)
print(json.dumps(_result), end="")
"""
)

# Keep a combined constant for introspection / tests.
_HARNESS_TEMPLATE = _HARNESS_PREFIX + "# (user code)" + _HARNESS_SUFFIX


# ---------------------------------------------------------------------------
# Runtime block
# ---------------------------------------------------------------------------


class CodeBlock(BaseBlock):
    """
    Execute user-provided Python code in an isolated subprocess.

    The code MUST define ``def main(data) -> <json-serializable>``.
    ``data`` is a dict with keys ``results``, ``metadata``, ``shared_memory``
    from the current :class:`WorkflowState`.

    Security:
        * AST validation rejects dangerous imports / builtins at init time.
        * Execution happens in a subprocess with a minimal environment.
        * A configurable timeout (default 30 s) kills runaway processes.

    No LLM calls — cost and tokens are unchanged.
    """

    def __init__(
        self,
        block_id: str,
        code: str,
        timeout_seconds: int = 30,
        allowed_imports: Optional[List[str]] = None,
    ):
        super().__init__(block_id)
        if not code or not code.strip():
            raise ValueError("Code cannot be empty")
        self.code = code
        self.timeout_seconds = timeout_seconds
        self.allowed_imports = (
            allowed_imports if allowed_imports is not None else list(DEFAULT_ALLOWED_IMPORTS)
        )
        self._validate_code()

    def _validate_code(self) -> None:
        """Validate user code via AST analysis."""
        _validate_code_ast(self.code, self.allowed_imports)

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        """Execute block with BlockContext, return BlockOutput."""
        stdout_bytes, stderr_bytes, returncode = await self._run_subprocess(ctx.inputs)

        if returncode != 0:
            error_msg = stderr_bytes.decode(errors="replace").strip()
            return BlockOutput(
                output=f"Error: {error_msg}",
                exit_handle="error",
                cost_usd=0.0,
                total_tokens=0,
                log_entries=[
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] CodeBlock: error — {error_msg}",
                    }
                ],
            )

        stdout = stdout_bytes.decode(errors="replace").strip()
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            return BlockOutput(
                output=f"Error: output is not valid JSON: {stdout!r}",
                cost_usd=0.0,
                total_tokens=0,
                log_entries=[
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] CodeBlock: non-JSON output",
                    }
                ],
            )

        exit_handle: Optional[str] = None
        if isinstance(result, dict) and "exit_handle" in result:
            raw = result["exit_handle"]
            if isinstance(raw, str):
                result.pop("exit_handle")
                exit_handle = raw if raw else None

        return BlockOutput(
            output=json.dumps(result) if not isinstance(result, str) else result,
            exit_handle=exit_handle,
            cost_usd=0.0,
            total_tokens=0,
            log_entries=[
                {
                    "role": "system",
                    "content": f"[Block {self.block_id}] CodeBlock: executed successfully",
                }
            ],
        )

    async def _run_subprocess(self, inputs: Dict[str, Any]) -> tuple:
        """Run the user code subprocess with the given inputs dict. Returns (stdout, stderr, returncode)."""
        import os

        harness = _HARNESS_PREFIX + self.code + _HARNESS_SUFFIX
        stdin_data = json.dumps(inputs).encode()

        minimal_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")}
        for key in ("HOME", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
            if key in os.environ:
                minimal_env[key] = os.environ[key]

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                harness,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=minimal_env,
            )

            async def _communicate():
                return await proc.communicate(input=stdin_data)

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                _communicate(), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise TimeoutError(
                f"CodeBlock '{self.block_id}': execution timed out after {self.timeout_seconds}s"
            )

        return stdout_bytes, stderr_bytes, proc.returncode


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class CodeBlockDef(BaseBlockDef):
    type: Literal["code"] = "code"
    code: str
    timeout_seconds: int = 30
    allowed_imports: Optional[List[str]] = None


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402

_register_block_def("code", CodeBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: CodeBlockDef,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
    **_: Any,
) -> CodeBlock:
    """Build a CodeBlock from a block definition."""
    if not block_def.code:
        raise ValueError(f"CodeBlock '{block_id}': code is required")
    return CodeBlock(
        block_id,
        code=block_def.code,
        timeout_seconds=block_def.timeout_seconds,
        allowed_imports=block_def.allowed_imports,
    )


_register_builder("code", build)
