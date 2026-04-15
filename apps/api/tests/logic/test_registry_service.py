import os
import tempfile
from pathlib import Path

from runsight_api.logic.services.registry_service import RegistryService


def test_discover_steps_directory_with_py_files():
    with tempfile.TemporaryDirectory() as tmp:
        steps_dir = Path(tmp) / "custom" / "steps"
        steps_dir.mkdir(parents=True)
        (steps_dir / "hello_world.py").write_text("# step")
        (steps_dir / "fetch_data.py").write_text("# step")
        (steps_dir / "__init__.py").write_text("")
        (steps_dir / ".hidden.py").write_text("# hidden")

        service = RegistryService(custom_dir=os.path.join(tmp, "custom"))
        result = service.discover_steps()

        ids = {s["id"] for s in result}
        names = {s["name"] for s in result}
        assert "hello_world" in ids
        assert "fetch_data" in ids
        assert "__init__" not in ids
        assert ".hidden" not in ids
        assert "Hello World" in names
        assert "Fetch Data" in names
        assert all(s["type"] == "step" for s in result)
        assert len(result) == 2


def test_discover_steps_empty_directory():
    with tempfile.TemporaryDirectory() as tmp:
        steps_dir = Path(tmp) / "custom" / "steps"
        steps_dir.mkdir(parents=True)

        service = RegistryService(custom_dir=os.path.join(tmp, "custom"))
        result = service.discover_steps()

        assert result == []


def test_discover_steps_directory_does_not_exist():
    with tempfile.TemporaryDirectory() as tmp:
        service = RegistryService(custom_dir=os.path.join(tmp, "custom"))
        result = service.discover_steps()
        assert result == []


def test_discover_steps_file_stem_as_id_and_name():
    with tempfile.TemporaryDirectory() as tmp:
        steps_dir = Path(tmp) / "custom" / "steps"
        steps_dir.mkdir(parents=True)
        (steps_dir / "my_cool_step.py").write_text("# step")

        service = RegistryService(custom_dir=os.path.join(tmp, "custom"))
        result = service.discover_steps()

        assert len(result) == 1
        assert result[0]["id"] == "my_cool_step"
        assert result[0]["name"] == "My Cool Step"
        assert result[0]["path"].endswith("my_cool_step.py")


def test_discover_steps_skips_init_and_dotfiles():
    with tempfile.TemporaryDirectory() as tmp:
        steps_dir = Path(tmp) / "custom" / "steps"
        steps_dir.mkdir(parents=True)
        (steps_dir / "__init__.py").write_text("")
        (steps_dir / ".secret.py").write_text("")
        (steps_dir / "valid.py").write_text("")

        service = RegistryService(custom_dir=os.path.join(tmp, "custom"))
        result = service.discover_steps()

        assert len(result) == 1
        assert result[0]["id"] == "valid"
