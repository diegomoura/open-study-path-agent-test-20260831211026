#!/usr/bin/env python3
"""Validate topic-first roadmaps and resumable external publication state."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from planning_publication_safety import (
    publication_state_violations,
    topic_first_violations,
)

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        fail(f"missing planning/publication safety file: {path}")
    return target.read_text(encoding="utf-8")


def require_terms(path: str, terms: list[str]) -> None:
    content = read(path)
    for term in terms:
        if term not in content:
            fail(f"{path} is missing required safety term: {term}")


def validate_contract() -> None:
    require_terms(
        "instructions/31-topic-first-safe-publication.md",
        [
            "`planning.unit: topic` is authoritative",
            "optional free-text `path.time_constraints`",
            "does not authorize silently removing mastery-required topics",
            "collect the minimum missing scheduling details at activation",
            "Never create `tmp`, `test`, `probe`",
            "After each successful external creation or update",
            "Continue a organização da minha trilha nas ferramentas que escolhemos.",
        ],
    )
    require_terms(
        "AGENTS.md",
        [
            "instructions/31-topic-first-safe-publication.md",
            "Do not create fixed durations in weeks",
            "must not silently remove mastery-required content",
            "Never create disposable external probe resources.",
        ],
    )
    require_terms(
        "templates/roadmap.md",
        [
            "Topics are the structural planning unit.",
            "optional free-text time constraint",
            "must not silently remove mastery-required content",
        ],
    )
    workflow = read(".github/workflows/validate-template.yml")
    for command in [
        "python scripts/validate_planning_publication_safety.py",
        "python scripts/test_planning_publication_safety.py",
    ]:
        if command not in workflow:
            fail(f"validation workflow is missing: {command}")


def validate_instance() -> None:
    config_path = ROOT / "study.config.yml"
    roadmap_path = ROOT / "study/roadmap.md"
    state_path = ROOT / "state/integrations.json"
    if not config_path.is_file():
        return

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        fail("study.config.yml must contain an object")

    if roadmap_path.is_file():
        violations = topic_first_violations(
            config, roadmap_path.read_text(encoding="utf-8")
        )
        if violations:
            fail(
                "topic-based planning cannot contain an implicit weekly structure; "
                "use total/topic effort or mark an explicitly requested optional projection"
            )

    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        violations = publication_state_violations(config, state)
        if violations:
            fail("; ".join(violations))


def main() -> None:
    validate_contract()
    validate_instance()
    print("Topic-first planning and resumable publication safety passed.")


if __name__ == "__main__":
    main()
