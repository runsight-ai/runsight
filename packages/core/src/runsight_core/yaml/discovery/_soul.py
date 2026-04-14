from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Collection

import yaml
from pydantic import ValidationError

from runsight_core.primitives import Soul
from runsight_core.yaml.discovery._base import BaseScanner, ScanIndex, ScanResult

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

        if not isinstance(soul_data, dict):
            raise _fail_soul_file(path, "invalid soul metadata")
        return self._parse_soul_mapping(path, soul_data)

    def _scan_yaml_content(self, path: Path, raw_yaml: str) -> ScanResult[Soul] | None:
        try:
            soul_data = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            raise _fail_soul_file(path, "malformed YAML") from exc

        if soul_data is None:
            return None
        if not isinstance(soul_data, dict):
            raise _fail_soul_file(path, "invalid soul metadata")

        soul = self._parse_soul_mapping(path, soul_data)
        resolved = path.resolve()
        try:
            relative_path = resolved.relative_to(self.base_dir.resolve()).as_posix()
        except ValueError:
            relative_path = path.as_posix()
        return ScanResult(
            path=resolved,
            stem=soul.id,
            relative_path=relative_path,
            item=soul,
            aliases=frozenset({soul.id}),
            entity_id=soul.id,
        )

    def _parse_soul_mapping(self, path: Path, soul_data: dict[str, Any]) -> Soul:
        try:
            soul = Soul.model_validate(soul_data)
        except ValidationError as exc:
            raise _fail_soul_file(path, str(exc)) from exc

        if soul.id != path.stem:
            raise _fail_soul_file(
                path,
                f"embedded id '{soul.id}' does not match filename stem '{path.stem}'",
            )

        return soul

    def _scan_filesystem(self) -> ScanIndex[Soul]:
        asset_dir = self.asset_dir
        if not asset_dir.exists():
            return ScanIndex()

        results: list[ScanResult[Soul]] = []
        seen_ids: set[str] = set()
        for yaml_file in self._glob_yaml_files(asset_dir):
            result = self._scan_yaml_file(yaml_file)
            if result is not None:
                if result.entity_id in seen_ids:
                    raise _fail_soul_file(
                        yaml_file,
                        f"duplicate custom soul id collision for {result.entity_id!r}",
                    )
                seen_ids.add(result.entity_id)
                results.append(result)
        return ScanIndex(results)

    def _scan_git(self, git_ref: str, git_service: Any) -> ScanIndex[Soul]:
        command = [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            git_ref,
            "--",
            f"{self.asset_subdir}/",
        ]
        result = subprocess.run(
            command,
            cwd=str(git_service.repo_path),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return ScanIndex()

        results: list[ScanResult[Soul]] = []
        seen_ids: set[str] = set()
        for line in result.stdout.splitlines():
            candidate = line.strip()
            if not candidate or not candidate.endswith(".yaml"):
                continue
            candidate_path = Path(candidate)
            try:
                raw_yaml = git_service.read_file(candidate, git_ref)
            except Exception:
                continue
            result_item = self._scan_yaml_content(candidate_path, raw_yaml)
            if result_item is not None:
                if result_item.entity_id in seen_ids:
                    raise _fail_soul_file(
                        candidate_path,
                        f"duplicate custom soul id collision for {result_item.entity_id!r}",
                    )
                seen_ids.add(result_item.entity_id)
                results.append(result_item)
        return ScanIndex(results)

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

        for soul_key in sorted(ignored_soul_keys & set(index.ids())):
            logger.warning("Inline soul '%s' overrides external soul file", soul_key)
        return index.without_ids(ignored_soul_keys)
