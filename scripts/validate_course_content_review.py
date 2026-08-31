#!/usr/bin/env python3
"""Validate the reusable and generated course-content review contract."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml

from course_content_review import validate_repository

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        fail(f"missing course-content review file: {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, terms: list[str]) -> None:
    content = read(path)
    for term in terms:
        if term not in content:
            fail(f"{path} is missing course-content review term: {term}")


def validate_reusable_contract() -> None:
    require(
        "instructions/36-review-course-content.md",
        [
            "course-content reviewer",
            "Does the delivered course teach and assess what the approved plan promised",
            "direct prerequisites",
            "does not assume linear order",
            "blocking_findings",
            "content_version",
            "semantic honesty",
        ],
    )
    require(
        "instructions/35-review-curriculum.md",
        [
            "instructions/36-review-course-content.md",
            "curriculum architecture",
            "materialized teaching content",
        ],
    )
    require(
        "instructions/30-generate-path.md",
        [
            "stable learning outcome IDs",
            "open-study-path:outcome",
            "state/content-reviews/",
            "instructions/36-review-course-content.md",
        ],
    )
    require(
        "instructions/57-materialize-next-content.md",
        [
            "instructions/36-review-course-content.md",
            "state/content-reviews/",
            "current content version",
        ],
    )
    require(
        "instructions/40-publish-tasks.md",
        [
            "Pré-requisitos desta etapa:",
            "numeração dos cartões",
            "direct prerequisites",
        ],
    )
    future_card = read("instructions/40-publish-tasks.md")
    if "Esta etapa vem depois de <pré-requisitos em linguagem simples>." in future_card:
        fail("future task copy must not imply a linear previous-step sequence")
    if "quando você concluir as etapas anteriores" in future_card:
        fail("future task copy must refer to explicit prerequisites, not all previous stages")

    require(
        "AGENTS.md",
        [
            "Independent course-content review",
            "direct prerequisite list",
            "state/content-reviews/",
        ],
    )
    require(
        "docs/learner-facing-language.md",
        [
            "Numeração não é pré-requisito",
            "Pré-requisitos desta etapa",
        ],
    )

    manifest = yaml.safe_load(read("instructions/manifest.yml"))
    phases = {
        phase.get("id"): phase
        for phase in manifest.get("phases", [])
        if isinstance(phase, dict) and phase.get("id")
    }
    for phase_id in ["generate", "evaluate"]:
        if phases.get(phase_id, {}).get("internal_content_review") != "instructions/36-review-course-content.md":
            fail(f"{phase_id} must reference the independent course-content review")

    instance_template = yaml.safe_load(read("templates/instance.yml"))
    review = instance_template.get("content_review", {})
    expected = {
        "contract_version": 1,
        "required_for_materialized_topics": True,
        "independent_pass": True,
        "require_outcome_traceability": True,
    }
    for key, value in expected.items():
        if review.get(key) != value:
            fail(f"templates/instance.yml content_review.{key} must be {value!r}")

    workflow = read(".github/workflows/validate-template.yml")
    for command in [
        "python scripts/test_course_content_review.py",
        "python scripts/validate_course_content_review.py",
    ]:
        if command not in workflow:
            fail(f"validation workflow is missing: {command}")


def main() -> None:
    validate_reusable_contract()
    result = validate_repository(ROOT)
    if not result.ok:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Independent course-content review and outcome traceability passed.")


if __name__ == "__main__":
    main()
