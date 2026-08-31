#!/usr/bin/env python3
"""Validate or refresh only the latest approved review owner of each artifact."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "state" / "reviews"


@dataclass
class ReviewEntry:
    manifest: Path
    reviewed_at: datetime
    artifact: dict[str, Any]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_reviewed_at(value: Any, manifest: Path) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(
                f"{manifest.relative_to(ROOT)} has invalid reviewed_at: {value}"
            ) from exc
    else:
        raise ValueError(f"{manifest.relative_to(ROOT)} is missing reviewed_at")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def review_manifests() -> tuple[Path, ...]:
    return tuple(
        sorted({*REVIEWS.glob("*.yml"), *REVIEWS.glob("*.yaml")})
    )


def load_entries() -> tuple[dict[Path, dict[str, Any]], list[ReviewEntry], list[str]]:
    documents: dict[Path, dict[str, Any]] = {}
    entries: list[ReviewEntry] = []
    errors: list[str] = []
    if not REVIEWS.exists():
        return documents, entries, errors

    for manifest in review_manifests():
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            errors.append(
                f"invalid review manifest {manifest.relative_to(ROOT)}: {exc}"
            )
            continue
        if not isinstance(data, dict) or data.get("status") != "approved":
            continue
        try:
            reviewed_at = parse_reviewed_at(data.get("reviewed_at"), manifest)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        documents[manifest] = data
        artifacts = data.get("artifacts") or []
        if not isinstance(artifacts, list):
            continue
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            relative = artifact.get("path")
            change = artifact.get("change", "current")
            if not isinstance(relative, str) or change not in {"current", "deleted"}:
                continue
            entries.append(ReviewEntry(manifest, reviewed_at, artifact))
    return documents, entries, errors


def select_current_owners(
    entries: list[ReviewEntry],
) -> tuple[dict[str, ReviewEntry], list[str]]:
    owners: dict[str, ReviewEntry] = {}
    errors: list[str] = []
    for entry in entries:
        relative = str(entry.artifact["path"])
        previous = owners.get(relative)
        if previous is None or entry.reviewed_at > previous.reviewed_at:
            owners[relative] = entry
            continue
        if entry.reviewed_at == previous.reviewed_at and entry.manifest != previous.manifest:
            errors.append(
                "ambiguous current review owner for "
                f"{relative}: {previous.manifest.relative_to(ROOT)} and "
                f"{entry.manifest.relative_to(ROOT)} share reviewed_at"
            )
    return owners, errors


def validate_or_refresh(write: bool) -> tuple[int, int, list[str]]:
    documents, entries, errors = load_entries()
    owners, owner_errors = select_current_owners(entries)
    errors.extend(owner_errors)
    stale = 0
    changed_manifests: set[Path] = set()

    for relative, entry in sorted(owners.items()):
        target = (ROOT / relative).resolve()
        try:
            target.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"unsafe reviewed artifact path: {relative}")
            continue

        change = entry.artifact.get("change", "current")
        label = entry.manifest.relative_to(ROOT)
        if change == "deleted":
            if target.exists():
                stale += 1
                errors.append(
                    f"{label} is the latest owner of {relative} as deleted, but the file exists"
                )
            continue

        if not target.is_file():
            stale += 1
            errors.append(
                f"{label} is the latest owner of missing artifact: {relative}"
            )
            continue

        recorded = entry.artifact.get("sha256")
        current = digest(target)
        if recorded == current:
            continue

        stale += 1
        print(
            f"STALE CURRENT OWNER {label}: {relative}: {recorded} -> {current}"
        )
        if write:
            entry.artifact["sha256"] = current
            changed_manifests.add(entry.manifest)

    if write:
        for manifest in sorted(changed_manifests):
            manifest.write_text(
                yaml.safe_dump(
                    documents[manifest], sort_keys=False, allow_unicode=True
                ),
                encoding="utf-8",
            )
    return stale, len(changed_manifests), errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="refresh only the latest approved review owner for each current artifact",
    )
    args = parser.parse_args()

    stale, changed, errors = validate_or_refresh(args.write)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if args.write:
        print(f"Refreshed {changed} current-owner review manifest(s).")
        return 1 if errors else 0
    if stale or errors:
        print(
            "ERROR: current review ownership is stale; create or refresh the latest operation review",
            file=sys.stderr,
        )
        return 1
    print(
        "Current review ownership is consistent; historical reviews remain immutable."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
