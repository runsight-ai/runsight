import importlib
import sys
from pathlib import Path
from textwrap import dedent
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from runsight_core.primitives import Soul

_API_SRC = Path(__file__).resolve().parents[3] / "apps" / "api" / "src" / "runsight_api"
for module_name, module_path in {
    "runsight_api": _API_SRC,
    "runsight_api.core": _API_SRC / "core",
    "runsight_api.data": _API_SRC / "data",
    "runsight_api.data.filesystem": _API_SRC / "data" / "filesystem",
    "runsight_api.domain": _API_SRC / "domain",
}.items():
    if module_name not in sys.modules:
        module = ModuleType(module_name)
        module.__path__ = [str(module_path)]
        sys.modules[module_name] = module

if "structlog" not in sys.modules:
    structlog_stub = ModuleType("structlog")
    structlog_stub.contextvars = SimpleNamespace(
        bind_contextvars=lambda **_: None,
        unbind_contextvars=lambda *_, **__: None,
    )
    sys.modules["structlog"] = structlog_stub

if "ruamel" not in sys.modules:
    ruamel_stub = ModuleType("ruamel")
    ruamel_yaml_stub = ModuleType("ruamel.yaml")

    class _YAML:
        pass

    ruamel_yaml_stub.YAML = _YAML
    ruamel_stub.yaml = ruamel_yaml_stub
    sys.modules["ruamel"] = ruamel_stub
    sys.modules["ruamel.yaml"] = ruamel_yaml_stub

if "sqlmodel" not in sys.modules:
    sqlmodel_stub = ModuleType("sqlmodel")

    class _SQLModel:
        metadata = SimpleNamespace(
            create_all=lambda *_args, **_kwargs: None,
            drop_all=lambda *_args, **_kwargs: None,
        )

    sqlmodel_stub.SQLModel = _SQLModel
    sqlmodel_stub.create_engine = lambda *args, **kwargs: SimpleNamespace(args=args, kwargs=kwargs)
    sys.modules["sqlmodel"] = sqlmodel_stub

WorkflowRepository = importlib.import_module(
    "runsight_api.data.filesystem.workflow_repo"
).WorkflowRepository


def test_validate_yaml_content_uses_public_soul_scanner(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    raw_yaml = dedent(
        """\
        version: "1.0"
        blocks:
          step:
            type: linear
            soul_ref: researcher
        workflow:
          name: scanner_migration
          entry: step
          transitions:
            - from: step
              to: null
        """
    )

    with patch("runsight_api.data.filesystem.workflow_repo.SoulScanner") as mock_scanner:
        mock_scanner.return_value.scan.return_value.stems.return_value = {
            "researcher": Soul(
                id="researcher_1",
                role="Researcher",
                system_prompt="Research",
            )
        }
        valid, error = repo._validate_yaml_content("scanner-migration", raw_yaml)

    assert valid is True
    assert error is None
    mock_scanner.assert_called_once()
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.stems.assert_called_once()
