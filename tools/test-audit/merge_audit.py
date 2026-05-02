from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "current-test-inventory.tsv"
SHARD_INPUTS = ROOT / "shard-inputs"
SHARDS = ROOT / "shards"
OUTPUT = ROOT / "full-test-cleanup-map.tsv"

FIELDNAMES = [
    "path",
    "workspace",
    "loc",
    "extension",
    "current_behavior",
    "alignment_status",
    "primary_action",
    "reason",
    "mirror_or_duplicate_of",
    "fixture_plan",
    "verification_target",
    "confidence",
]

REVIEW_FIELDNAMES = [
    "path",
    "loc",
    "current_behavior",
    "alignment_status",
    "primary_action",
    "reason",
    "mirror_or_duplicate_of",
    "fixture_plan",
    "verification_target",
    "confidence",
]

EXPECTED_SHARDS = [
    "api",
    "core-1",
    "core-2",
    "core-3",
    "gui",
    "shared-ui",
    "e2e-tools",
]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> None:
    inventory = read_tsv(INVENTORY)
    inventory_by_path = {row["path"]: row for row in inventory}
    if len(inventory_by_path) != len(inventory):
        fail("inventory contains duplicate paths")

    assigned_paths: list[str] = []
    for shard in EXPECTED_SHARDS:
        input_path = SHARD_INPUTS / f"{shard}.tsv"
        if not input_path.exists():
            fail(f"missing shard input {input_path}")
        assigned_paths.extend(row["path"] for row in read_tsv(input_path))

    assigned_counter = Counter(assigned_paths)
    duplicate_assignments = sorted(path for path, count in assigned_counter.items() if count > 1)
    if duplicate_assignments:
        fail(f"duplicate assigned paths: {duplicate_assignments[:10]}")
    if set(assigned_paths) != set(inventory_by_path):
        missing = sorted(set(inventory_by_path) - set(assigned_paths))
        extra = sorted(set(assigned_paths) - set(inventory_by_path))
        fail(f"assignment mismatch: missing={missing[:10]} extra={extra[:10]}")

    merged: list[dict[str, str]] = []
    reviewed_paths: list[str] = []
    for shard in EXPECTED_SHARDS:
        shard_path = SHARDS / f"{shard}.tsv"
        if not shard_path.exists():
            fail(f"missing reviewed shard {shard_path}")
        rows = read_tsv(shard_path)
        if rows and list(rows[0].keys()) != REVIEW_FIELDNAMES:
            fail(f"{shard_path} header does not match expected review schema")

        expected_paths = [row["path"] for row in read_tsv(SHARD_INPUTS / f"{shard}.tsv")]
        actual_paths = [row["path"] for row in rows]
        if actual_paths != expected_paths:
            missing = sorted(set(expected_paths) - set(actual_paths))
            extra = sorted(set(actual_paths) - set(expected_paths))
            fail(f"{shard} path mismatch: missing={missing[:10]} extra={extra[:10]}")

        for row in rows:
            source = inventory_by_path[row["path"]]
            if row["loc"] != source["loc"]:
                fail(f"{row['path']} LOC mismatch: inventory={source['loc']} review={row['loc']}")
            reviewed_paths.append(row["path"])
            merged.append(
                {
                    "path": row["path"],
                    "workspace": source["workspace"],
                    "loc": source["loc"],
                    "extension": source["extension"],
                    "current_behavior": row["current_behavior"],
                    "alignment_status": row["alignment_status"],
                    "primary_action": row["primary_action"],
                    "reason": row["reason"],
                    "mirror_or_duplicate_of": row["mirror_or_duplicate_of"],
                    "fixture_plan": row["fixture_plan"],
                    "verification_target": row["verification_target"],
                    "confidence": row["confidence"],
                }
            )

    review_counter = Counter(reviewed_paths)
    duplicate_reviews = sorted(path for path, count in review_counter.items() if count > 1)
    if duplicate_reviews:
        fail(f"duplicate reviewed paths: {duplicate_reviews[:10]}")
    if set(reviewed_paths) != set(inventory_by_path):
        missing = sorted(set(inventory_by_path) - set(reviewed_paths))
        extra = sorted(set(reviewed_paths) - set(inventory_by_path))
        fail(f"review mismatch: missing={missing[:10]} extra={extra[:10]}")

    merged.sort(key=lambda row: row["path"])
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=FIELDNAMES,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(merged)

    by_action = Counter(row["primary_action"] for row in merged)
    by_status = Counter(row["alignment_status"] for row in merged)
    print(f"wrote {OUTPUT} with {len(merged)} reviewed test files")
    print("actions:", dict(sorted(by_action.items())))
    print("statuses:", dict(sorted(by_status.items())))


if __name__ == "__main__":
    main()
