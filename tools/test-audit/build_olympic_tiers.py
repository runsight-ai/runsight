from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "full-test-cleanup-map.tsv"
OUTPUT = ROOT / "olympic-tiers"

TIERS = [
    ("tier-1-bronze-delete.tsv", "DELETE"),
    ("tier-2-silver-merge-then-delete.tsv", "MERGE_THEN_DELETE"),
    ("tier-3-silver-move-to-tooling.tsv", "MOVE_TO_TOOLING"),
    ("tier-4-gold-shrink-to-smoke.tsv", "SHRINK_TO_SMOKE"),
    ("tier-5-gold-split-god-suites.tsv", "SPLIT"),
    ("tier-6-platinum-externalize-fixtures.tsv", "EXTERNALIZE_FIXTURES"),
    ("tier-7-diamond-deep-review.tsv", "REVIEW_DEEP"),
]


def main() -> None:
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise SystemExit(f"no audit rows found in {SOURCE}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())

    for filename, action in TIERS:
        selected = sorted(
            [row for row in rows if row["primary_action"] == action],
            key=lambda row: (row["workspace"], row["path"]),
        )
        with (OUTPUT / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fields,
                delimiter="\t",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(selected)
        print(filename, len(selected), dict(Counter(row["workspace"] for row in selected)))


if __name__ == "__main__":
    main()
