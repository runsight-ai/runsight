import tempfile
import os
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


def test_discover_tasks_directory_with_py_files():
    with tempfile.TemporaryDirectory() as tmp:
        tasks_dir = Path(tmp) / "custom" / "tasks"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "train_model.py").write_text("# task")
        (tasks_dir / "deploy_task.py").write_text("# task")

        service = RegistryService(custom_dir=os.path.join(tmp, "custom"))
        result = service.discover_tasks()

        assert len(result) == 2
        ids = {t["id"] for t in result}
        assert "train_model" in ids
        assert "deploy_task" in ids
        assert all(t["type"] == "task" for t in result)
        assert "Train Model" in {t["name"] for t in result}


def test_discover_tasks_empty_directory():
    with tempfile.TemporaryDirectory() as tmp:
        tasks_dir = Path(tmp) / "custom" / "tasks"
        tasks_dir.mkdir(parents=True)

        service = RegistryService(custom_dir=os.path.join(tmp, "custom"))
        result = service.discover_tasks()
        assert result == []


def test_discover_tasks_directory_does_not_exist():
    with tempfile.TemporaryDirectory() as tmp:
        service = RegistryService(custom_dir=os.path.join(tmp, "custom"))
        result = service.discover_tasks()
        assert result == []


def test_get_all_returns_both_steps_and_tasks():
    with tempfile.TemporaryDirectory() as tmp:
        steps_dir = Path(tmp) / "custom" / "steps"
        tasks_dir = Path(tmp) / "custom" / "tasks"
        steps_dir.mkdir(parents=True)
        tasks_dir.mkdir(parents=True)
        (steps_dir / "step_one.py").write_text("")
        (tasks_dir / "task_one.py").write_text("")

        service = RegistryService(custom_dir=os.path.join(tmp, "custom"))
        result = service.get_all()

        assert "steps" in result
        assert "tasks" in result
        assert len(result["steps"]) == 1
        assert len(result["tasks"]) == 1
        assert result["steps"][0]["id"] == "step_one"
        assert result["tasks"][0]["id"] == "task_one"
