"""Red-team tests for RUN-859: Standardize API router conventions.

Covers:
1. eval.py and models.py must use prefix= in APIRouter()
2. eval.py and models.py must use PascalCase tags ("Eval", "Models")
3. All endpoint functions in eval.py and models.py must be async def
4. No inline Pydantic schema classes (BaseModel subclasses) in any router file
5. GET /api/models must return {items: [...], total: N} wrapped shape (not bare list)
"""

import ast
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport import routers as routers_pkg

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROUTERS_DIR = Path(routers_pkg.__file__).parent


def _read_router_source(name: str) -> str:
    return (_ROUTERS_DIR / f"{name}.py").read_text()


def _parse_router_call(source: str) -> ast.Call | None:
    """Return the AST Call node for APIRouter(...) if present."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # Matches: APIRouter(...)
            if isinstance(func, ast.Name) and func.id == "APIRouter":
                return node
            # Matches: fastapi.APIRouter(...)
            if isinstance(func, ast.Attribute) and func.attr == "APIRouter":
                return node
    return None


def _get_router_kwarg(call: ast.Call, kwarg_name: str) -> ast.expr | None:
    """Return the AST value node for a given keyword argument in an ast.Call."""
    for kw in call.keywords:
        if kw.arg == kwarg_name:
            return kw.value
    return None


def _get_string_value(node: ast.expr | None) -> str | None:
    """Extract string constant from an AST node (handles Constant and List)."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _get_list_string_values(node: ast.expr | None) -> list[str]:
    """Extract string values from an AST List node."""
    if node is None or not isinstance(node, ast.List):
        return []
    return [
        elt.value
        for elt in node.elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    ]


def _get_endpoint_function_names(source: str) -> list[tuple[str, bool]]:
    """Return list of (name, is_async) for all route-decorated functions."""
    tree = ast.parse(source)
    results = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check if decorated with @router.get/post/put/delete/patch
            for deco in node.decorator_list:
                is_router_deco = False
                if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
                    if isinstance(deco.func.value, ast.Name) and deco.func.value.id == "router":
                        is_router_deco = True
                if is_router_deco:
                    results.append((node.name, isinstance(node, ast.AsyncFunctionDef)))
                    break
    return results


def _get_inline_basemodel_classes(source: str) -> list[str]:
    """Return names of classes that subclass BaseModel defined in the file."""
    tree = ast.parse(source)
    inline_classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                # Matches: class Foo(BaseModel):
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    inline_classes.append(node.name)
                # Matches: class Foo(pydantic.BaseModel):
                if isinstance(base, ast.Attribute) and base.attr == "BaseModel":
                    inline_classes.append(node.name)
    return inline_classes


# ===========================================================================
# 1. Router prefix= tests
# ===========================================================================


class TestRouterPrefix:
    """All routers must declare prefix= in their APIRouter() call."""

    def test_eval_router_has_prefix(self):
        """eval.py APIRouter() must include a prefix= keyword argument."""
        source = _read_router_source("eval")
        call = _parse_router_call(source)
        assert call is not None, "APIRouter() call not found in eval.py"
        prefix_node = _get_router_kwarg(call, "prefix")
        assert prefix_node is not None, (
            "eval.py APIRouter() is missing prefix= argument. Add prefix='/eval' to the router."
        )
        prefix_value = _get_string_value(prefix_node)
        assert prefix_value is not None, "eval.py prefix= must be a string literal"
        assert prefix_value.startswith("/"), (
            f"eval.py prefix must start with '/'. Got: {prefix_value!r}"
        )

    def test_models_router_has_prefix(self):
        """models.py APIRouter() must include a prefix= keyword argument."""
        source = _read_router_source("models")
        call = _parse_router_call(source)
        assert call is not None, "APIRouter() call not found in models.py"
        prefix_node = _get_router_kwarg(call, "prefix")
        assert prefix_node is not None, (
            "models.py APIRouter() is missing prefix= argument. Add prefix='/models' to the router."
        )
        prefix_value = _get_string_value(prefix_node)
        assert prefix_value is not None, "models.py prefix= must be a string literal"
        assert prefix_value.startswith("/"), (
            f"models.py prefix must start with '/'. Got: {prefix_value!r}"
        )


# ===========================================================================
# 2. PascalCase tag tests
# ===========================================================================


class TestRouterPascalCaseTags:
    """All routers must use PascalCase for their tags."""

    def _extract_tag(self, source: str) -> str | None:
        call = _parse_router_call(source)
        if call is None:
            return None
        tags_node = _get_router_kwarg(call, "tags")
        if tags_node is None:
            return None
        # tags= can be a list like ["Eval"] or a bare string "Eval"
        if isinstance(tags_node, ast.List):
            values = _get_list_string_values(tags_node)
            return values[0] if values else None
        return _get_string_value(tags_node)

    def test_eval_router_uses_pascal_case_tag(self):
        """eval.py tag must be 'Eval', not 'eval'."""
        source = _read_router_source("eval")
        tag = self._extract_tag(source)
        assert tag is not None, "eval.py APIRouter() has no tags= argument"
        assert tag == tag[0].upper() + tag[1:], (
            f"eval.py tag must be PascalCase. Got: {tag!r}. Expected: 'Eval'"
        )
        assert tag != "eval", "eval.py tag is lowercase 'eval'. Must be PascalCase 'Eval'."

    def test_models_router_uses_pascal_case_tag(self):
        """models.py tag must be 'Models', not 'models'."""
        source = _read_router_source("models")
        tag = self._extract_tag(source)
        assert tag is not None, "models.py APIRouter() has no tags= argument"
        assert tag == tag[0].upper() + tag[1:], (
            f"models.py tag must be PascalCase. Got: {tag!r}. Expected: 'Models'"
        )
        assert tag != "models", "models.py tag is lowercase 'models'. Must be PascalCase 'Models'."


# ===========================================================================
# 3. Async endpoint tests
# ===========================================================================


class TestEndpointsAreAsync:
    """All route handler functions must use async def."""

    def test_eval_endpoints_are_async(self):
        """Every @router.<method> decorated function in eval.py must be async def."""
        source = _read_router_source("eval")
        endpoints = _get_endpoint_function_names(source)
        assert len(endpoints) > 0, "No route-decorated functions found in eval.py"
        sync_endpoints = [name for name, is_async in endpoints if not is_async]
        assert sync_endpoints == [], (
            f"eval.py has sync (non-async) endpoints: {sync_endpoints}. "
            "All endpoint functions must use 'async def'."
        )

    def test_models_endpoints_are_async(self):
        """Every @router.<method> decorated function in models.py must be async def."""
        source = _read_router_source("models")
        endpoints = _get_endpoint_function_names(source)
        assert len(endpoints) > 0, "No route-decorated functions found in models.py"
        sync_endpoints = [name for name, is_async in endpoints if not is_async]
        assert sync_endpoints == [], (
            f"models.py has sync (non-async) endpoints: {sync_endpoints}. "
            "All endpoint functions must use 'async def'."
        )


# ===========================================================================
# 4. No inline schemas in routers
# ===========================================================================


class TestNoInlineSchemasInRouters:
    """Router files must not define Pydantic BaseModel subclasses inline."""

    _ROUTER_NAMES = ["eval", "models", "settings", "git"]

    @pytest.mark.parametrize("router_name", _ROUTER_NAMES)
    def test_no_inline_basemodel_in_router(self, router_name: str):
        """Router files must not contain inline class Foo(BaseModel) definitions."""
        source = _read_router_source(router_name)
        inline = _get_inline_basemodel_classes(source)
        assert inline == [], (
            f"{router_name}.py defines inline Pydantic schemas: {inline}. "
            "Move them to transport/schemas/{router_name}.py."
        )


# ===========================================================================
# 5. List response shape — models must return wrapped {items, total}
# ===========================================================================


class TestModelsListResponseShape:
    """GET /api/models must return a wrapped {items, total} shape, not a bare list."""

    def test_models_list_returns_wrapped_shape(self):
        """GET /api/models must return {items: [...], total: N}."""
        from runsight_api.transport.deps import get_model_service

        mock_service = Mock()
        mock_service.get_available_models.return_value = []
        app.dependency_overrides[get_model_service] = lambda: mock_service
        try:
            response = client.get("/api/models")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict), (
                f"GET /api/models must return a dict {{items, total}}, got {type(data).__name__}"
            )
            assert "items" in data, "GET /api/models response must contain 'items' key"
            assert "total" in data, "GET /api/models response must contain 'total' key"
            assert isinstance(data["items"], list), "'items' field must be a list"
            assert isinstance(data["total"], int), "'total' field must be an integer"
        finally:
            app.dependency_overrides.clear()

    def test_models_list_total_matches_items_count(self):
        """total must equal len(items) in the /api/models response."""
        from types import SimpleNamespace

        from runsight_api.transport.deps import get_model_service

        mock_model = SimpleNamespace(
            provider="openai",
            provider_name="Openai",
            model_id="gpt-4o",
            mode="chat",
            max_tokens=4096,
            input_cost_per_token=0.00003,
            output_cost_per_token=0.00006,
            supports_vision=False,
            supports_function_calling=True,
        )
        mock_service = Mock()
        mock_service.get_available_models.return_value = [mock_model, mock_model]
        app.dependency_overrides[get_model_service] = lambda: mock_service
        try:
            response = client.get("/api/models")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == len(data["items"]), (
                f"total ({data['total']}) must equal len(items) ({len(data['items'])})"
            )
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 6. Schemas in transport/schemas/ — models schemas moved out
# ===========================================================================


class TestModelsSchemasMovedToSchemaModule:
    """ModelResponse and ProviderSummary must live in transport/schemas/models.py."""

    def test_model_response_importable_from_schemas(self):
        """ModelResponse must be importable from transport.schemas.models."""
        from runsight_api.transport.schemas.models import ModelResponse  # noqa: F401

    def test_provider_summary_importable_from_schemas(self):
        """ProviderSummary must be importable from transport.schemas.models."""
        from runsight_api.transport.schemas.models import ProviderSummary  # noqa: F401


# ===========================================================================
# 7. Dead schemas/settings.py cleaned up
# ===========================================================================


class TestDeadSettingsSchemasRemoved:
    """transport/schemas/settings.py must not contain stale dead schemas."""

    _DEAD_SCHEMA_NAMES = ["ProviderResponse", "FallbackTargetResponse", "SettingsResponse"]

    @pytest.mark.parametrize("class_name", _DEAD_SCHEMA_NAMES)
    def test_dead_schema_not_in_settings_schema_module(self, class_name: str):
        """Dead schemas from old settings.py must be removed."""
        schemas_dir = Path(routers_pkg.__file__).parent.parent / "schemas" / "settings.py"
        source = schemas_dir.read_text()
        tree = ast.parse(source)
        class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        assert class_name not in class_names, (
            f"transport/schemas/settings.py still contains dead schema '{class_name}'. "
            "Remove it as part of the settings.py schema cleanup."
        )
