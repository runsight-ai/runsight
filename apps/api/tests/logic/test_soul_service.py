from unittest.mock import Mock
import pytest
from runsight_api.logic.services.soul_service import SoulService
from runsight_api.domain.value_objects import SoulEntity
from runsight_api.domain.errors import SoulNotFound


# --- list_souls ---


def test_list_souls_empty():
    soul_repo = Mock()
    soul_repo.list_all.return_value = []
    service = SoulService(soul_repo)
    result = service.list_souls()
    assert result == []
    soul_repo.list_all.assert_called_once()


def test_list_souls_multiple():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="soul_1", name="Alpha"),
        SoulEntity(id="soul_2", name="Beta"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls()
    assert result == souls
    assert len(result) == 2


def test_list_souls_with_query_matches_id():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="soul_alpha", name="X"),
        SoulEntity(id="soul_beta", name="Y"),
        SoulEntity(id="soul_gamma", name="Z"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls(query="alpha")
    assert len(result) == 1
    assert result[0].id == "soul_alpha"


def test_list_souls_with_query_matches_name():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="s1", name="Alpha Soul"),
        SoulEntity(id="s2", name="Beta Soul"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls(query="alpha")
    assert len(result) == 1
    assert result[0].name == "Alpha Soul"


def test_list_souls_with_query_case_insensitive():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="SOUL_1", name="Test"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls(query="soul")
    assert len(result) == 1
    assert result[0].id == "SOUL_1"


def test_list_souls_with_query_no_name_attribute():
    soul_repo = Mock()
    soul_without_name = SoulEntity(id="s1")
    soul_without_name.name = None
    soul_repo.list_all.return_value = [soul_without_name]
    service = SoulService(soul_repo)
    result = service.list_souls(query="s1")
    assert len(result) == 1
    assert result[0].id == "s1"


# --- get_soul ---


def test_get_soul_exists():
    soul_repo = Mock()
    mock_soul = SoulEntity(id="soul_1", name="Test Soul")
    soul_repo.get_by_id.return_value = mock_soul
    service = SoulService(soul_repo)
    res = service.get_soul("soul_1")
    assert res is mock_soul
    assert res.id == "soul_1"
    soul_repo.get_by_id.assert_called_once_with("soul_1")


def test_get_soul_not_found_returns_none():
    soul_repo = Mock()
    soul_repo.get_by_id.return_value = None
    service = SoulService(soul_repo)
    res = service.get_soul("missing")
    assert res is None


# --- create_soul ---


def test_create_soul_happy_path():
    soul_repo = Mock()
    created = SoulEntity(id="soul_custom", name="Custom")
    soul_repo.create.return_value = created
    service = SoulService(soul_repo)
    result = service.create_soul({"id": "soul_custom", "name": "Custom"})
    assert result == created
    assert result.id == "soul_custom"
    soul_repo.create.assert_called_once()
    call_args = soul_repo.create.call_args[0][0]
    assert call_args["id"] == "soul_custom"
    assert call_args["name"] == "Custom"


def test_create_soul_missing_id_auto_generates():
    soul_repo = Mock()

    def capture_create(data):
        return SoulEntity(id=data["id"], name=data.get("name"))

    soul_repo.create.side_effect = capture_create
    service = SoulService(soul_repo)
    service.create_soul({"name": "Auto Soul"})
    call_args = soul_repo.create.call_args[0][0]
    assert call_args["id"].startswith("soul_")
    assert len(call_args["id"]) == len("soul_") + 8  # soul_ + 8 hex chars
    assert call_args["name"] == "Auto Soul"


def test_create_soul_empty_data_auto_generates_id():
    soul_repo = Mock()

    def capture_create(data):
        return SoulEntity(id=data["id"])

    soul_repo.create.side_effect = capture_create
    service = SoulService(soul_repo)
    service.create_soul({})
    call_args = soul_repo.create.call_args[0][0]
    assert "id" in call_args
    assert call_args["id"].startswith("soul_")


def test_create_soul_empty_string_id_auto_generates():
    soul_repo = Mock()

    def capture_create(data):
        return SoulEntity(id=data["id"])

    soul_repo.create.side_effect = capture_create
    service = SoulService(soul_repo)
    service.create_soul({"id": ""})
    call_args = soul_repo.create.call_args[0][0]
    assert call_args["id"].startswith("soul_")


# --- update_soul ---


def test_update_soul_happy_path():
    soul_repo = Mock()
    existing = SoulEntity(id="soul_1", name="Old")
    updated = SoulEntity(id="soul_1", name="New")
    soul_repo.get_by_id.return_value = existing
    soul_repo.update.return_value = updated
    service = SoulService(soul_repo)
    result = service.update_soul("soul_1", {"name": "New"})
    assert result == updated
    soul_repo.update.assert_called_once_with("soul_1", {"name": "New"})


def test_update_soul_not_found_raises_soul_not_found():
    soul_repo = Mock()
    soul_repo.get_by_id.return_value = None
    service = SoulService(soul_repo)
    with pytest.raises(SoulNotFound) as exc_info:
        service.update_soul("missing", {"name": "New"})
    assert "missing" in str(exc_info.value)
    soul_repo.update.assert_not_called()


def test_update_soul_copy_on_edit_creates_copy():
    soul_repo = Mock()
    existing = SoulEntity(id="soul_1", name="Original")
    soul_repo.get_by_id.return_value = existing

    def capture_create(data):
        return SoulEntity(id=data["id"], name=data.get("name", ""))

    soul_repo.create.side_effect = capture_create
    service = SoulService(soul_repo)
    service.update_soul("soul_1", {"name": "Copy"}, copy_on_edit=True)
    soul_repo.create.assert_called_once()
    call_args = soul_repo.create.call_args[0][0]
    assert call_args["id"].startswith("soul_1_copy_")
    assert len(call_args["id"]) == len("soul_1_copy_") + 4  # 4 hex chars
    assert call_args["name"] == "Copy"
    soul_repo.update.assert_not_called()


# --- delete_soul ---


def test_delete_soul_happy_path():
    soul_repo = Mock()
    soul_repo.delete.return_value = True
    service = SoulService(soul_repo)
    result = service.delete_soul("soul_1")
    assert result is True
    soul_repo.delete.assert_called_once_with("soul_1")


def test_delete_soul_not_found_raises_soul_not_found():
    soul_repo = Mock()
    soul_repo.delete.return_value = False
    service = SoulService(soul_repo)
    with pytest.raises(SoulNotFound) as exc_info:
        service.delete_soul("missing")
    assert "missing" in str(exc_info.value)
