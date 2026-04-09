from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Collection

import yaml
from pydantic import ValidationError

from runsight_core.primitives import Soul
from runsight_core.yaml.discovery._base import BaseScanner, ScanIndex

logger = logging.getLogger(__name__)


def _fail_soul_file(yaml_file: Path, message: str) -> ValueError:
    return ValueError(f"{yaml_file.name}: {message}")


class SoulScanner(BaseScanner[Soul]):
    """Scanner for soul YAML files."""

    def __init__(
        self,
        base_dir: str | Path,
        *,
        souls_subdir: str = "custom/souls",
    ) -> None:
        super().__init__(base_dir)
        self._souls_subdir = souls_subdir

    @property
    def asset_subdir(self) -> str:
        return self._souls_subdir

    def _parse_file(self, path: Path, raw_yaml: str) -> Soul:
        try:
            soul_data = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            raise _fail_soul_file(path, "malformed YAML") from exc

        try:
            return Soul.model_validate(soul_data)
        except ValidationError as exc:
            raise _fail_soul_file(path, str(exc)) from exc

    def _glob_yaml_files(self, directory: Path) -> list[Path]:
        # Keep historical discovery behavior: souls are discovered only from *.yaml files.
        return sorted(directory.glob("*.yaml"), key=lambda path: path.name)

    def scan(
        self,
        *,
        ignore_keys: Collection[str] | None = None,
        git_ref: str | None = None,
        git_service: Any = None,
    ) -> ScanIndex[Soul]:
        index = super().scan(git_ref=git_ref, git_service=git_service)
        ignored_soul_keys = set(ignore_keys or ())
        if not ignored_soul_keys:
            return index

        for soul_key in sorted(ignored_soul_keys & set(index.stems())):
            logger.warning("Inline soul '%s' overrides external soul file", soul_key)
        return index.without_stems(ignored_soul_keys)
