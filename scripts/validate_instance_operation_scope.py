#!/usr/bin/env python3
"""Reject mixed instance operations and excessively serial pull-request histories."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
INSTANCE_MARKER = ROOT / ".open-study-path/instance.yml"
REVIEW_PREFIX = "state/reviews/"

PROTECTED_EXACT = {
    "AGENTS.md",
    ".open-study-path/template.yml",
}
PROTECTED_PREFIXES = (
    ".github/workflows/",
    "scripts/",
    "instructions/",
    "templates/",
    "schemas/",
    "docs/",
)
CURRICULUM_PREFIXES = (
    "study/topics/",
    "study/modules/",
    "study/assessments/",
    ".github/ISSUE_TEMPLATE/assessment-topic-",
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def normalize(path: str) -> str:
    normalized = Path(path).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_protected(path: str) -> bool:
    normalized = normalize(path)
    return normalized in PROTECTED_EXACT or normalized.startswith(PROTECTED_PREFIXES)


def is_curriculum(path: str) -> bool:
    return normalize(path).startswith(CURRICULUM_PREFIXES)


def commit_budget_error(changed_count: int, commit_count: int) -> str | None:
    if changed_count >= 8 and commit_count > 8:
        return (
            f"large instance operation uses {commit_count} commits for {changed_count} files; "
            "rebuild the final tree as a batched commit"
        )
    return None


def migration_review_present(paths: Iterable[str]) -> bool:
    for relative in paths:
        normalized = normalize(relative)
        if not normalized.startswith(REVIEW_PREFIX) or not normalized.endswith((".yml", ".yaml")):
            continue
        target = ROOT / normalized
        if not target.is_file():
            continue
        try:
            document = yaml.safe_load(target.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(document, dict):
            continue
        if (
            document.get("phase") == "migration"
            and document.get("status") == "approved"
            and document.get("independent_pass") is True
        ):
            return True
    return False


def git_lines(*args: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        fail(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def main() -> None:
    if not INSTANCE_MARKER.is_file():
        print("Template mode: instance operation scope guard skipped.")
        return

    base_sha = os.environ.get("REVIEW_BASE_SHA", "").strip()
    if not base_sha or set(base_sha) == {"0"}:
        print("No review base SHA: instance operation scope guard skipped.")
        return

    changed = tuple(sorted({normalize(path) for path in git_lines("diff", "--name-only", f"{base_sha}...HEAD")}))
    if not changed:
        print("No changed files for instance operation scope guard.")
        return

    protected = tuple(path for path in changed if is_protected(path))
    curriculum = tuple(path for path in changed if is_curriculum(path))

    if protected and curriculum:
        fail(
            "instance pull request mixes reusable infrastructure with learner curriculum: "
            + ", ".join(protected)
        )

    if protected and not migration_review_present(changed):
        fail(
            "reusable instance infrastructure changed without an approved migration review: "
            + ", ".join(protected)
        )

    commit_lines = git_lines("rev-list", "--count", f"{base_sha}..HEAD")
    commit_count = int(commit_lines[0]) if commit_lines else 0
    budget_error = commit_budget_error(len(changed), commit_count)
    if budget_error:
        fail(budget_error)

    print(
        "Instance operation scope and commit budget passed "
        f"({len(changed)} file(s), {commit_count} commit(s))."
    )


if __name__ == "__main__":
    main()
