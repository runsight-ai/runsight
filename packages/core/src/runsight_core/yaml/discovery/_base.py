from __future__ import annotations

import abc
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Collection, Generic, TypeVar

import yaml

T = TypeVar("T")


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


class ScanIndex(Generic[T]):
    def __init__(self, results: Collection[ScanResult[T]] | None = None) -> None:
        self._results_by_stem: dict[str, ScanResult[T]] = {}
        self._lookup: dict[str, ScanResult[T]] = {}
        self._ordered_stems: list[str] = []
        if results:
            for result in results:
                self.add(result)

    def add(self, result: ScanResult[T]) -> None:
        if result.stem not in self._results_by_stem:
            self._ordered_stems.append(result.stem)
        self._results_by_stem[result.stem] = result
        for alias in result.aliases:
            self._lookup[alias] = result

    def get(self, ref: str) -> ScanResult[T] | None:
        return self._lookup.get(ref)

    def get_all(self) -> list[ScanResult[T]]:
        return [self._results_by_stem[stem] for stem in self._ordered_stems]

    def stems(self) -> dict[str, T]:
        return {stem: result.item for stem, result in self._results_by_stem.items()}

    def without_stems(self, keys: Collection[str]) -> ScanIndex[T]:
        keys_to_drop = set(keys)
        return ScanIndex(result for result in self.get_all() if result.stem not in keys_to_drop)


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

    def _compute_aliases(self, path: Path, item: T) -> set[str]:
        resolved = path.resolve()
        aliases = {resolved.as_posix(), path.stem}
        try:
            aliases.add(resolved.relative_to(self.base_dir.resolve()).as_posix())
        except ValueError:
            pass
        return aliases

    def scan(
        self,
        *,
        git_ref: str | None = None,
        git_service: Any = None,
    ) -> ScanIndex[T]:
        if git_ref is not None and git_service is not None:
            return self._scan_git(git_ref, git_service)
        return self._scan_filesystem()

    def _scan_filesystem(self) -> ScanIndex[T]:
        asset_dir = self.asset_dir
        if not asset_dir.exists():
            return ScanIndex()

        results: list[ScanResult[T]] = []
        for yaml_file in self._glob_yaml_files(asset_dir):
            result = self._scan_yaml_file(yaml_file)
            if result is not None:
                results.append(result)
        return ScanIndex(results)

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
        return ScanIndex(results)

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
        aliases = self._compute_aliases(path, item)
        resolved = path.resolve()
        try:
            relative_path = resolved.relative_to(self.base_dir.resolve()).as_posix()
        except ValueError:
            relative_path = path.as_posix()
        aliases.add(resolved.as_posix())
        aliases.add(path.stem)
        aliases.add(relative_path)
        return ScanResult(
            path=resolved,
            stem=path.stem,
            relative_path=relative_path,
            item=item,
            aliases=frozenset(aliases),
        )

    def _glob_yaml_files(self, directory: Path) -> list[Path]:
        candidates = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
        return sorted(
            {path.resolve(): path for path in candidates}.values(), key=lambda path: path.name
        )

    def _candidate_paths(self, ref: str) -> list[Path]:
        ref_path = Path(ref)
        if ref_path.is_absolute():
            return [ref_path.resolve()]

        root = self.base_dir.resolve()
        candidates: list[Path] = []
        if ref.startswith("custom/"):
            candidates.append((root / ref_path).resolve())
        else:
            candidates.append((self.asset_dir / ref_path).resolve())
            if ref_path.suffix == "":
                candidates.append((self.asset_dir / f"{ref}.yaml").resolve())
                candidates.append((self.asset_dir / f"{ref}.yml").resolve())
        deduped: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            candidate_str = candidate.as_posix()
            if candidate_str in seen:
                continue
            seen.add(candidate_str)
            deduped.append(candidate)
        return deduped

    def resolve_ref(
        self,
        ref: str,
        *,
        index: ScanIndex[T] | None = None,
        git_ref: str | None = None,
        git_service: Any = None,
    ) -> ScanResult[T] | None:
        if index is not None:
            indexed = index.get(ref)
            if indexed is not None:
                return indexed

        for candidate in self._candidate_paths(ref):
            scanned = self._load_candidate(candidate, git_ref=git_ref, git_service=git_service)
            if scanned is not None:
                return scanned
        return None

    def _load_candidate(
        self,
        candidate: Path,
        *,
        git_ref: str | None = None,
        git_service: Any = None,
    ) -> ScanResult[T] | None:
        if git_ref is not None and git_service is not None:
            try:
                raw_yaml = git_service.read_file(candidate.as_posix(), git_ref)
            except Exception:
                return None
            return self._scan_yaml_content(candidate, raw_yaml)

        if not candidate.exists():
            return None
        raw_yaml = candidate.read_text(encoding="utf-8")
        return self._scan_yaml_content(candidate, raw_yaml)
