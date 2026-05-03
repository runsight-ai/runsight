"""Write a package-level coverage summary from CI coverage artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parents[1]
COVERAGE_DIR = REPO_ROOT / "coverage"


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}%"


def _coverage_xml_percent(path: Path) -> float | None:
    if not path.exists():
        return None
    root = ElementTree.parse(path).getroot()
    if "line-rate" in root.attrib:
        return float(root.attrib["line-rate"]) * 100
    covered = root.attrib.get("lines-covered")
    valid = root.attrib.get("lines-valid")
    if covered is None or valid in {None, "0"}:
        return None
    return (float(covered) / float(valid)) * 100


def _vitest_summary_percent(path: Path) -> float | None:
    if not path.exists():
        return None
    summary = json.loads(path.read_text(encoding="utf-8"))
    value = summary.get("total", {}).get("lines", {}).get("pct")
    return float(value) if value is not None else None


def _package_rows() -> list[tuple[str, float | None]]:
    return [
        ("apps/api", _coverage_xml_percent(COVERAGE_DIR / "apps-api.xml")),
        ("packages/core", _coverage_xml_percent(COVERAGE_DIR / "packages-core.xml")),
        ("apps/gui", _vitest_summary_percent(COVERAGE_DIR / "apps-gui" / "coverage-summary.json")),
        (
            "packages/shared",
            _vitest_summary_percent(COVERAGE_DIR / "packages-shared" / "coverage-summary.json"),
        ),
        (
            "packages/ui",
            _vitest_summary_percent(COVERAGE_DIR / "packages-ui" / "coverage-summary.json"),
        ),
    ]


def main() -> None:
    COVERAGE_DIR.mkdir(exist_ok=True)
    lines = [
        "## Package Coverage",
        "",
        "| Package | Lines |",
        "|---|---:|",
    ]
    for package, percent in _package_rows():
        lines.append(f"| `{package}` | {_pct(percent)} |")
    lines.append("")

    summary = "\n".join(lines)
    (COVERAGE_DIR / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)

    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_step_summary:
        with Path(github_step_summary).open("a", encoding="utf-8") as handle:
            handle.write(summary + "\n")


if __name__ == "__main__":
    main()
