from __future__ import annotations

import abc
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Collection, Generic, TypeVar

import yaml

T = TypeVar("T")


def resolve_discovery_base_dir(start: Path) -> str:
    """Resolve the authoritative discovery base directory for a workflow location."""
    current = start.resolve()
    current_custom_dir = current / "custom"
    if current_custom_dir.is_dir():
        return str(current)

    for candidate in current.parents:
        custom_dir = candidate / "custom"
        if not custom_dir.is_dir():
            continue
        workflows_dir = candidate / "workflows"
        if current.is_relative_to(workflows_dir) or current.is_relative_to(custom_dir):
            return str(candidate)

    return str(current)


class AssetType(str, Enum):
    SOUL = "SOUL"
    TOOL = "TOOL"
    WORKFLOW = "WORKFLOW"


@dataclass(frozen=True, slots=True)
class ScanError:
    file_path: Path
    message: str


@dataclass(frozen=True, slots=True)
class ScanResult(Generic[T]):
    path: Path
    stem: str
    relative_path: str
    item: T
    aliases: frozenset[str]
    entity_id: str | None = None


class ScanIndex(Generic[T]):
    def __init__(self, results: Collection[ScanResult[T]] | None = None) -> None:
        self._results_by_entity_id: dict[str, ScanResult[T]] = {}
        self._lookup: dict[str, ScanResult[T]] = {}
        self._ordered_entity_ids: list[str] = []
        if results:
            for result in results:
                self.add(result)

    def _require_entity_id(self, result: ScanResult[T]) -> str:
        if not isinstance(result.entity_id, str) or not result.entity_id:
            raise ValueError(
                "scan result missing embedded entity id for "
                f"stem={result.stem!r} at {result.relative_path}"
            )
        return result.entity_id

    def add(self, result: ScanResult[T]) -> None:
        entity_id = self._require_entity_id(result)
        existing = self._results_by_entity_id.get(entity_id)
        if existing is not None and existing is not result:
            raise ValueError(
                "duplicate scan entity id collision for "
                f"{entity_id!r}: existing stem={existing.stem!r} at {existing.relative_path}, "
                f"new stem={result.stem!r} at {result.relative_path}"
            )

        existing_alias = self._lookup.get(entity_id)
        if existing_alias is not None and existing_alias is not result:
            raise ValueError(
                "duplicate scan alias collision for "
                f"{entity_id!r}: existing entity id={existing_alias.entity_id!r} "
                f"(stem={existing_alias.stem!r}, path={existing_alias.relative_path}), "
                f"new entity id={entity_id!r} (stem={result.stem!r}, path={result.relative_path})"
            )

        if entity_id not in self._results_by_entity_id:
            self._ordered_entity_ids.append(entity_id)
        self._results_by_entity_id[entity_id] = result
        self._lookup[entity_id] = result

    def _upsert(self, result: ScanResult[T]) -> None:
        entity_id = self._require_entity_id(result)
        if entity_id not in self._results_by_entity_id:
            self._ordered_entity_ids.append(entity_id)
        self._results_by_entity_id[entity_id] = result
        self._lookup[entity_id] = result

    def get(self, ref: str) -> ScanResult[T] | None:
        return self._lookup.get(ref)

    def get_all(self) -> list[ScanResult[T]]:
        return [self._results_by_entity_id[entity_id] for entity_id in self._ordered_entity_ids]

    def ids(self) -> dict[str, T]:
        return {entity_id: result.item for entity_id, result in self._results_by_entity_id.items()}

    def without_ids(self, keys: Collection[str]) -> ScanIndex[T]:
        keys_to_drop = set(keys)
        return ScanIndex(
            result for result in self.get_all() if result.entity_id not in keys_to_drop
        )


class BaseScanner(Generic[T], abc.ABC):
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    @property
    @abc.abstractmethod
    def asset_subdir(self) -> str:
        raise NotImplementedError

    @property
    def asset_dir(self) -> Path:
        return self.base_dir / self.asset_subdir

    @abc.abstractmethod
    def _parse_file(self, path: Path, raw_yaml: str) -> T:
        raise NotImplementedError

    @property
    def reject_duplicate_entity_ids(self) -> bool:
        return False

    def scan(
        self,
        *,
        git_ref: str | None = None,
        git_service: Any = None,
    ) -> ScanIndex[T]:
        if git_ref is not None and git_service is not None:
            return self._scan_git(git_ref, git_service)
        return self._scan_filesystem()

    def _build_scan_index(self, results: Collection[ScanResult[T]]) -> ScanIndex[T]:
        index = ScanIndex()
        for result in results:
            if self.reject_duplicate_entity_ids:
                index.add(result)
            else:
                index._upsert(result)
        return index

    def _scan_filesystem(self) -> ScanIndex[T]:
        asset_dir = self.asset_dir
        if not asset_dir.exists():
            return ScanIndex()

        results: list[ScanResult[T]] = []
        for yaml_file in self._glob_yaml_files(asset_dir):
            result = self._scan_yaml_file(yaml_file)
            if result is not None:
                results.append(result)
        return self._build_scan_index(results)

    def _scan_git(self, git_ref: str, git_service: Any) -> ScanIndex[T]:
        asset_dir = self.asset_dir
        if not asset_dir.exists():
            # The git ref may still be valid even if the local checkout lacks the directory,
            # so only short-circuit when we know we cannot enumerate.
            pass

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

        results: list[ScanResult[T]] = []
        for line in result.stdout.splitlines():
            candidate = line.strip()
            if not candidate or not candidate.endswith((".yaml", ".yml")):
                continue
            try:
                raw_yaml = git_service.read_file(candidate, git_ref)
            except Exception:
                continue
            result_item = self._scan_yaml_content(Path(candidate), raw_yaml)
            if result_item is not None:
                results.append(result_item)
        return self._build_scan_index(results)

    def _scan_yaml_file(self, path: Path) -> ScanResult[T] | None:
        raw_yaml = path.read_text(encoding="utf-8")
        return self._scan_yaml_content(path, raw_yaml)

    def _scan_yaml_content(self, path: Path, raw_yaml: str) -> ScanResult[T] | None:
        try:
            parsed = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            raise ValueError(f"{path.name}: malformed YAML") from exc

        if parsed is None:
            return None
        if not isinstance(parsed, dict):
            raise ValueError(f"{path.name}: YAML content is not a mapping")

        item = self._parse_file(path, raw_yaml)
        entity_id = getattr(item, "id", None)
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError(f"{path.name}: parsed item does not expose an embedded id")
        resolved = path.resolve()
        try:
            relative_path = resolved.relative_to(self.base_dir.resolve()).as_posix()
        except ValueError:
            relative_path = path.as_posix()
        return ScanResult(
            path=resolved,
            stem=path.stem,
            entity_id=entity_id,
            relative_path=relative_path,
            item=item,
            aliases=frozenset({entity_id}),
        )

    def _glob_yaml_files(self, directory: Path) -> list[Path]:
        candidates = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
        return sorted(
            {path.resolve(): path for path in candidates}.values(), key=lambda path: path.name
        )

    def resolve_ref(
        self,
        ref: str,
        *,
        index: ScanIndex[T] | None = None,
    ) -> ScanResult[T] | None:
        if index is not None:
            return index.get(ref)
        return None
