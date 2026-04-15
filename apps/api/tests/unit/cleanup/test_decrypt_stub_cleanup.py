"""Red tests for RUN-412: delete legacy decrypt stubs and decrypt-patching tests."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # apps/api
_SRC = _ROOT / "src" / "runsight_api" / "logic" / "services"

_SERVICE_FILES = [
    _SRC / "provider_service.py",
    _SRC / "execution_service.py",
]

_LEGACY_TEST_FILES = [
    _ROOT / "tests" / "unit" / "logic" / "test_provider_service_wiring.py",
    _ROOT / "tests" / "logic" / "test_execution_service_concurrency.py",
]


def _read_text(path: Path) -> str:
    assert path.exists(), f"Expected file to exist: {path}"
    return path.read_text()


def _find_lines_matching(path: Path, pattern: re.Pattern[str]) -> list[str]:
    hits: list[str] = []
    for line_no, line in enumerate(_read_text(path).splitlines(), 1):
        if pattern.search(line):
            hits.append(f"{path}:{line_no}: {line.strip()}")
    return hits


class TestNoLegacyDecryptStubs:
    def test_no_decrypt_none_assignments_remain(self):
        pattern = re.compile(r"\bdecrypt\s*=\s*None\b")
        hits = [
            hit
            for service_file in _SERVICE_FILES
            for hit in _find_lines_matching(service_file, pattern)
        ]
        assert hits == [], "Legacy decrypt stub assignments still remain:\n" + "\n".join(hits)

    def test_no_legacy_stub_comment_remains(self):
        patterns = [
            re.compile(r"Legacy stubs"),
            re.compile(r"negative-assertion tests can patch them"),
        ]
        hits: list[str] = []
        for service_file in _SERVICE_FILES:
            text = _read_text(service_file)
            for line_no, line in enumerate(text.splitlines(), 1):
                if any(pattern.search(line) for pattern in patterns):
                    hits.append(f"{service_file}:{line_no}: {line.strip()}")
        assert hits == [], "Legacy stub comment still remains:\n" + "\n".join(hits)


class TestNoDecryptPatchingTestsRemain:
    def test_no_decrypt_patching_lines_remain(self):
        pattern = re.compile(r"\bpatch\b.*\bdecrypt\b|\bdecrypt\b.*\bpatch\b")
        hits: list[str] = []
        for legacy_test_file in _LEGACY_TEST_FILES:
            hits.extend(_find_lines_matching(legacy_test_file, pattern))
        assert hits == [], "Decrypt-patching tests still remain:\n" + "\n".join(hits)
