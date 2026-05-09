"""Workspace materializer filesystem safety behavior."""

from __future__ import annotations

import importlib
import os
import socket
import stat
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError


def _contract(name: str) -> type[Any]:
    isolation = importlib.import_module("runsight_core.isolation")
    exports = set(getattr(isolation, "__all__", ()))

    assert hasattr(isolation, name), f"runsight_core.isolation must expose {name}"
    assert name in exports, f"runsight_core.isolation.__all__ must include {name}"
    return getattr(isolation, name)


def _assert_materialization_rejects(action: Any) -> None:
    with pytest.raises(
        (FileExistsError, IsADirectoryError, PermissionError, ValueError, ValidationError)
    ):
        action()


def _session(tmp_path: Path):
    WorkspaceSession = _contract("WorkspaceSession")

    host_root = (tmp_path / "workspace").resolve()
    host_root.mkdir()
    return WorkspaceSession(
        id="session-fixture",
        host_root=host_root,
        runtime_root=host_root,
        runtime_workdir=host_root,
        cleanup=True,
    )


def _manifest(materializations: list[Any], *, working_dir: str = "."):
    WorkspaceManifest = _contract("WorkspaceManifest")

    return WorkspaceManifest(materializations=materializations, working_dir=working_dir)


def _materialization(path: str, *, content: str = "payload", overwrite: bool = False):
    WorkspaceMaterialization = _contract("WorkspaceMaterialization")

    return WorkspaceMaterialization(path=path, content=content, mode=0o600, overwrite=overwrite)


def test_materializer_rejects_symlink_path_components_under_workspace_root(tmp_path: Path) -> None:
    WorkspaceMaterializer = _contract("WorkspaceMaterializer")

    session = _session(tmp_path)
    real_directory = session.host_root / "real"
    real_directory.mkdir()
    (session.host_root / "link").symlink_to(real_directory, target_is_directory=True)

    _assert_materialization_rejects(
        lambda: WorkspaceMaterializer(session).materialize(
            _manifest([_materialization("link/created.txt")])
        )
    )

    assert not (real_directory / "created.txt").exists()


def test_materializer_rejects_existing_file_when_overwrite_is_false(tmp_path: Path) -> None:
    WorkspaceMaterializer = _contract("WorkspaceMaterializer")

    session = _session(tmp_path)
    target = session.host_root / "existing.txt"
    target.write_text("old", encoding="utf-8")

    _assert_materialization_rejects(
        lambda: WorkspaceMaterializer(session).materialize(
            _manifest([_materialization("existing.txt", content="new", overwrite=False)])
        )
    )

    assert target.read_text(encoding="utf-8") == "old"


def test_materializer_overwrites_regular_files_when_overwrite_is_true(tmp_path: Path) -> None:
    WorkspaceMaterializer = _contract("WorkspaceMaterializer")

    session = _session(tmp_path)
    target = session.host_root / "existing.txt"
    target.write_text("old", encoding="utf-8")

    WorkspaceMaterializer(session).materialize(
        _manifest([_materialization("existing.txt", content="new", overwrite=True)])
    )

    assert target.read_text(encoding="utf-8") == "new"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_materializer_never_overwrites_directories_or_symlinks(tmp_path: Path) -> None:
    WorkspaceMaterializer = _contract("WorkspaceMaterializer")

    session = _session(tmp_path)
    (session.host_root / "directory").mkdir()
    (session.host_root / "symlink").symlink_to(
        session.host_root / "directory", target_is_directory=True
    )
    materializer = WorkspaceMaterializer(session)

    for unsafe_path in ("directory", "symlink"):
        _assert_materialization_rejects(
            lambda unsafe_path=unsafe_path: materializer.materialize(
                _manifest([_materialization(unsafe_path, overwrite=True)])
            )
        )

    assert (session.host_root / "directory").is_dir()
    assert (session.host_root / "symlink").is_symlink()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO fixture requires POSIX mkfifo")
def test_materializer_never_overwrites_fifos(tmp_path: Path) -> None:
    WorkspaceMaterializer = _contract("WorkspaceMaterializer")

    session = _session(tmp_path)
    fifo_path = session.host_root / "pipe"
    os.mkfifo(fifo_path)

    _assert_materialization_rejects(
        lambda: WorkspaceMaterializer(session).materialize(
            _manifest([_materialization("pipe", overwrite=True)])
        )
    )

    assert stat.S_ISFIFO(fifo_path.lstat().st_mode)


def test_materializer_never_overwrites_sockets(tmp_path: Path) -> None:
    WorkspaceMaterializer = _contract("WorkspaceMaterializer")

    session = _session(tmp_path)
    socket_path = session.host_root / "service.sock"
    unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        unix_socket.bind(str(socket_path))

        _assert_materialization_rejects(
            lambda: WorkspaceMaterializer(session).materialize(
                _manifest([_materialization("service.sock", overwrite=True)])
            )
        )

        assert stat.S_ISSOCK(socket_path.lstat().st_mode)
    finally:
        unix_socket.close()


def test_materializer_creates_and_validates_workspace_working_directory(tmp_path: Path) -> None:
    WorkspaceMaterializer = _contract("WorkspaceMaterializer")

    session = _session(tmp_path)

    WorkspaceMaterializer(session).materialize(
        _manifest([_materialization("nested/work/output.txt")], working_dir="nested/work")
    )

    assert session.runtime_workdir == session.runtime_root / "nested" / "work"
    assert session.runtime_workdir.is_dir()
    assert (session.host_root / "nested" / "work" / "output.txt").read_text(
        encoding="utf-8"
    ) == "payload"


def test_materializer_enforces_policy_materialization_size_before_writes(
    tmp_path: Path,
) -> None:
    WorkspaceMaterializer = _contract("WorkspaceMaterializer")
    WorkspacePolicy = _contract("WorkspacePolicy")

    session = _session(tmp_path)

    with pytest.raises(ValueError, match="max_materialization_bytes"):
        WorkspaceMaterializer(session).materialize(
            _manifest(
                [
                    _materialization("small.txt", content="1234"),
                    _materialization("large.txt", content="5678"),
                ]
            ),
            policy=WorkspacePolicy(max_materialization_bytes=7),
        )

    assert not (session.host_root / "small.txt").exists()
    assert not (session.host_root / "large.txt").exists()


def test_materializer_rejects_working_directory_that_resolves_to_file(tmp_path: Path) -> None:
    WorkspaceMaterializer = _contract("WorkspaceMaterializer")

    session = _session(tmp_path)

    _assert_materialization_rejects(
        lambda: WorkspaceMaterializer(session).materialize(
            _manifest(
                [_materialization("nested/work", content="payload")], working_dir="nested/work"
            )
        )
    )
