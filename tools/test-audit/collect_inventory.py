from __future__ import annotations

import csv
from pathlib import Path

ROOTS = [
    ("api", Path("apps/api/tests")),
    ("core", Path("packages/core/tests")),
    ("tools", Path("tools/tests")),
    ("gui", Path("apps/gui/src")),
    ("shared", Path("packages/shared/src")),
    ("ui", Path("packages/ui/src")),
    ("e2e", Path("testing/gui-e2e")),
]

PATTERNS = ("*test*.py", "*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx")
OUTPUT = Path("tools/test-audit/current-test-inventory.tsv")


def main() -> None:
    rows: set[tuple[str, str, str, str]] = set()
    for workspace, root in ROOTS:
        if not root.exists():
            continue
        for pattern in PATTERNS:
            for path in root.rglob(pattern):
                if "__pycache__" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                loc = text.count("\n") + (1 if text else 0)
                rows.add((path.as_posix(), workspace, str(loc), path.suffix))

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["path", "workspace", "loc", "extension"])
        writer.writerows(sorted(rows))

    print(f"wrote {OUTPUT} with {len(rows)} rows")


if __name__ == "__main__":
    main()
