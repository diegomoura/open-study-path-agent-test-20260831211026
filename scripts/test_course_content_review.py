#!/usr/bin/env python3
"""Behavioral regressions for independent course-content review."""

from __future__ import annotations

from copy import deepcopy

from course_content_review import validate_materialized_topic


def topic() -> dict:
    return {
        "id": "TOPIC-009",
        "content_status": "materialized",
        "content_version": 2,
        "prerequisites": ["TOPIC-003", "TOPIC-005", "TOPIC-007"],
        "learning_outcomes": [
            {
                "id": "LO-1",
                "statement": "Definir critérios de avaliação observáveis.",
                "required_concepts": ["caso de teste", "critério"],
            },
            {
                "id": "LO-2",
                "statement": "Detectar uma regressão comparando resultados.",
                "required_concepts": ["baseline", "regressão"],
            },
        ],
    }


def module() -> str:
    return """# Evals

<!-- open-study-path:outcome LO-1 -->
## Critérios
Conteúdo real que ensina critérios e casos.

<!-- open-study-path:outcome LO-2 -->
## Regressões
Conteúdo real que ensina baseline e comparação.
"""


def rubric() -> dict:
    return {
        "topic_id": "TOPIC-009",
        "questions": [
            {"id": "q1", "outcome_ids": ["LO-1"]},
            {"id": "q2", "outcome_ids": ["LO-1"]},
            {"id": "q3", "outcome_ids": ["LO-2"]},
            {"id": "q4", "outcome_ids": ["LO-2"]},
            {"id": "q5", "outcome_ids": ["LO-1", "LO-2"]},
        ],
    }


def review() -> dict:
    return {
        "version": 1,
        "topic_id": "TOPIC-009",
        "content_version": 2,
        "reviewed_at": "2026-07-30T09:00:00Z",
        "reviewer_role": "course_content_reviewer",
        "review_mode": "independent_pass",
        "status": "approved",
        "checks": {
            "scope_alignment": "passed",
            "prerequisite_integrity": "passed",
            "outcome_coverage": "passed",
            "lesson_assessment_alignment": "passed",
            "deliverable_alignment": "passed",
            "learner_navigation": "passed",
            "level_progression": "passed",
            "source_quality": "passed",
            "practice_consistency": "passed",
        },
        "prerequisites_reviewed": ["TOPIC-003", "TOPIC-005", "TOPIC-007"],
        "navigation": {
            "direct_prerequisites_only": True,
            "does_not_assume_linear_order": True,
        },
        "outcome_coverage": [
            {
                "outcome_id": "LO-1",
                "status": "covered",
                "assessment_questions": ["q1", "q2", "q5"],
            },
            {
                "outcome_id": "LO-2",
                "status": "covered",
                "assessment_questions": ["q3", "q4", "q5"],
            },
        ],
        "blocking_findings": [],
        "non_blocking_findings": [],
    }


def assert_error(result, text: str) -> None:
    assert any(text in error for error in result.errors), result.errors


def test_complete_review_passes() -> None:
    result = validate_materialized_topic(topic(), module(), rubric(), review())
    assert result.ok, result.errors


def test_missing_planned_outcome_content_is_blocking() -> None:
    lesson = module().replace("<!-- open-study-path:outcome LO-2 -->\n", "")
    result = validate_materialized_topic(topic(), lesson, rubric(), review())
    assert_error(result, "missing outcome markers")


def test_assessment_must_cover_every_outcome() -> None:
    assessment = rubric()
    for question in assessment["questions"]:
        question["outcome_ids"] = ["LO-1"]
    result = validate_materialized_topic(topic(), module(), assessment, review())
    assert_error(result, "outcomes are not assessed")


def test_stale_review_cannot_approve_changed_content() -> None:
    evidence = review()
    evidence["content_version"] = 1
    result = validate_materialized_topic(topic(), module(), rubric(), evidence)
    assert_error(result, "review is stale")


def test_review_must_use_actual_direct_prerequisites() -> None:
    evidence = review()
    evidence["prerequisites_reviewed"] = ["TOPIC-008"]
    result = validate_materialized_topic(topic(), module(), rubric(), evidence)
    assert_error(result, "review prerequisites do not match")


def test_linear_order_assumption_blocks_approval() -> None:
    evidence = review()
    evidence["navigation"]["does_not_assume_linear_order"] = False
    result = validate_materialized_topic(topic(), module(), rubric(), evidence)
    assert_error(result, "confirm non-linear navigation")


def test_blocking_finding_cannot_be_hidden_by_approved_status() -> None:
    evidence = review()
    evidence["blocking_findings"] = [
        {"code": "OUTCOME_MISSING", "message": "A aula não ensina o resultado prometido."}
    ]
    result = validate_materialized_topic(topic(), module(), rubric(), evidence)
    assert_error(result, "unresolved blocking findings")


def test_review_mapping_must_match_rubric() -> None:
    evidence = review()
    evidence["outcome_coverage"][0]["assessment_questions"] = ["q1"]
    result = validate_materialized_topic(topic(), module(), rubric(), evidence)
    assert_error(result, "assessment mapping is stale")


def main() -> None:
    test_complete_review_passes()
    test_missing_planned_outcome_content_is_blocking()
    test_assessment_must_cover_every_outcome()
    test_stale_review_cannot_approve_changed_content()
    test_review_must_use_actual_direct_prerequisites()
    test_linear_order_assumption_blocks_approval()
    test_blocking_finding_cannot_be_hidden_by_approved_status()
    test_review_mapping_must_match_rubric()
    print("Course-content reviewer behavioral regressions passed.")


if __name__ == "__main__":
    main()
