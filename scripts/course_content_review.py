#!/usr/bin/env python3
"""Validate outcome traceability and durable independent course-content reviews."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping

import yaml

OUTCOME_ID = re.compile(r"^LO-[1-9][0-9]*$")
OUTCOME_MARKER = re.compile(
    r"<!--\s*open-study-path:outcome\s+(LO-[1-9][0-9]*)\s*-->",
    re.IGNORECASE,
)
REQUIRED_CHECKS = (
    "scope_alignment",
    "prerequisite_integrity",
    "outcome_coverage",
    "lesson_assessment_alignment",
    "deliverable_alignment",
    "learner_navigation",
    "level_progression",
    "source_quality",
    "practice_consistency",
)


@dataclass(frozen=True)
class ReviewResult:
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing YAML frontmatter: {path}")
    try:
        _, raw, body = text.split("---", 2)
    except ValueError as exc:
        raise ValueError(f"malformed YAML frontmatter: {path}") from exc
    document = yaml.safe_load(raw)
    if not isinstance(document, dict):
        raise ValueError(f"frontmatter must be an object: {path}")
    return document, body


def review_enabled(instance: Mapping[str, Any]) -> bool:
    review = _mapping(instance.get("content_review"))
    return (
        review.get("contract_version") == 1
        and review.get("required_for_materialized_topics") is True
        and review.get("require_outcome_traceability") is True
    )


def outcome_contract_errors(topic: Mapping[str, Any]) -> tuple[list[str], dict[str, Mapping[str, Any]]]:
    errors: list[str] = []
    topic_id = _text(topic.get("id")) or "<unknown-topic>"
    raw_outcomes = _list(topic.get("learning_outcomes"))
    outcomes: dict[str, Mapping[str, Any]] = {}

    if not raw_outcomes:
        errors.append(f"{topic_id} must define learning_outcomes")
        return errors, outcomes

    if not 1 <= len(raw_outcomes) <= 7:
        errors.append(f"{topic_id} must define between 1 and 7 learning outcomes")

    for raw in raw_outcomes:
        outcome = _mapping(raw)
        outcome_id = _text(outcome.get("id"))
        if not OUTCOME_ID.fullmatch(outcome_id):
            errors.append(f"{topic_id} has invalid learning outcome id: {outcome_id or '<missing>'}")
            continue
        if outcome_id in outcomes:
            errors.append(f"{topic_id} has duplicate learning outcome id: {outcome_id}")
            continue
        statement = _text(outcome.get("statement"))
        concepts = [_text(value) for value in _list(outcome.get("required_concepts")) if _text(value)]
        if not statement:
            errors.append(f"{topic_id} outcome {outcome_id} is missing a statement")
        if not concepts:
            errors.append(f"{topic_id} outcome {outcome_id} must define required_concepts")
        outcomes[outcome_id] = outcome

    return errors, outcomes


def validate_materialized_topic(
    topic: Mapping[str, Any],
    module_text: str,
    rubric: Mapping[str, Any],
    review: Mapping[str, Any],
) -> ReviewResult:
    errors, outcomes = outcome_contract_errors(topic)
    topic_id = _text(topic.get("id")) or "<unknown-topic>"
    content_version = topic.get("content_version")
    outcome_ids = set(outcomes)

    markers = [value.upper() for value in OUTCOME_MARKER.findall(module_text)]
    marker_set = set(markers)
    missing_markers = sorted(outcome_ids - marker_set)
    unknown_markers = sorted(marker_set - outcome_ids)
    duplicate_markers = sorted({value for value in markers if markers.count(value) > 1})
    if missing_markers:
        errors.append(f"{topic_id} module is missing outcome markers: {missing_markers}")
    if unknown_markers:
        errors.append(f"{topic_id} module contains unknown outcome markers: {unknown_markers}")
    if duplicate_markers:
        errors.append(f"{topic_id} module repeats outcome markers: {duplicate_markers}")

    rubric_questions = _list(rubric.get("questions"))
    assessed_by: dict[str, set[str]] = {outcome_id: set() for outcome_id in outcome_ids}
    known_question_ids: set[str] = set()
    for raw_question in rubric_questions:
        question = _mapping(raw_question)
        question_id = _text(question.get("id"))
        if question_id:
            known_question_ids.add(question_id)
        mapped = [_text(value) for value in _list(question.get("outcome_ids")) if _text(value)]
        if not mapped:
            errors.append(f"{topic_id} rubric question {question_id or '<missing>'} has no outcome_ids")
        for outcome_id in mapped:
            if outcome_id not in outcome_ids:
                errors.append(
                    f"{topic_id} rubric question {question_id or '<missing>'} references unknown outcome {outcome_id}"
                )
                continue
            assessed_by[outcome_id].add(question_id)

    unassessed = sorted(outcome_id for outcome_id, questions in assessed_by.items() if not questions)
    if unassessed:
        errors.append(f"{topic_id} outcomes are not assessed: {unassessed}")

    if review.get("version") != 1:
        errors.append(f"{topic_id} review must use version 1")
    if _text(review.get("topic_id")) != topic_id:
        errors.append(f"{topic_id} review topic_id mismatch")
    if review.get("content_version") != content_version:
        errors.append(
            f"{topic_id} review is stale: expected content_version {content_version}, "
            f"got {review.get('content_version')}"
        )
    if not _text(review.get("reviewed_at")):
        errors.append(f"{topic_id} review is missing reviewed_at")
    if _text(review.get("reviewer_role")) != "course_content_reviewer":
        errors.append(f"{topic_id} review must use reviewer_role course_content_reviewer")
    if _text(review.get("review_mode")) != "independent_pass":
        errors.append(f"{topic_id} review must use review_mode independent_pass")
    if _text(review.get("status")) != "approved":
        errors.append(f"{topic_id} review status must be approved")

    checks = _mapping(review.get("checks"))
    for check in REQUIRED_CHECKS:
        if _text(checks.get(check)) != "passed":
            errors.append(f"{topic_id} review check must pass: {check}")

    prerequisites = [_text(value) for value in _list(topic.get("prerequisites"))]
    reviewed_prerequisites = [_text(value) for value in _list(review.get("prerequisites_reviewed"))]
    if reviewed_prerequisites != prerequisites:
        errors.append(
            f"{topic_id} review prerequisites do not match the topic contract: "
            f"expected {prerequisites}, got {reviewed_prerequisites}"
        )

    navigation = _mapping(review.get("navigation"))
    if navigation.get("direct_prerequisites_only") is not True:
        errors.append(f"{topic_id} review must confirm direct prerequisites only")
    if navigation.get("does_not_assume_linear_order") is not True:
        errors.append(f"{topic_id} review must confirm non-linear navigation")

    blocking = _list(review.get("blocking_findings"))
    if blocking:
        errors.append(f"{topic_id} review has unresolved blocking findings")

    raw_coverage = _list(review.get("outcome_coverage"))
    coverage: dict[str, Mapping[str, Any]] = {}
    for raw in raw_coverage:
        entry = _mapping(raw)
        outcome_id = _text(entry.get("outcome_id"))
        if outcome_id in coverage:
            errors.append(f"{topic_id} review duplicates outcome coverage: {outcome_id}")
            continue
        coverage[outcome_id] = entry

    if set(coverage) != outcome_ids:
        errors.append(
            f"{topic_id} review outcome coverage mismatch: expected {sorted(outcome_ids)}, "
            f"got {sorted(coverage)}"
        )

    for outcome_id in sorted(outcome_ids):
        entry = _mapping(coverage.get(outcome_id))
        if _text(entry.get("status")) != "covered":
            errors.append(f"{topic_id} review outcome {outcome_id} must be covered")
        recorded_questions = {
            _text(value) for value in _list(entry.get("assessment_questions")) if _text(value)
        }
        if not recorded_questions:
            errors.append(f"{topic_id} review outcome {outcome_id} has no assessment questions")
        unknown_questions = sorted(recorded_questions - known_question_ids)
        if unknown_questions:
            errors.append(
                f"{topic_id} review outcome {outcome_id} references unknown questions: {unknown_questions}"
            )
        expected_questions = assessed_by.get(outcome_id, set())
        if recorded_questions != expected_questions:
            errors.append(
                f"{topic_id} review outcome {outcome_id} assessment mapping is stale: "
                f"expected {sorted(expected_questions)}, got {sorted(recorded_questions)}"
            )

    return ReviewResult(tuple(errors))


def template_contract_errors(root: Path) -> list[str]:
    errors: list[str] = []
    topic_path = root / "templates" / "topic.md"
    module_path = root / "templates" / "module.md"
    rubric_path = root / "templates" / "assessment-rubric.yml"
    review_path = root / "templates" / "content-review.yml"

    for path in [topic_path, module_path, rubric_path, review_path]:
        if not path.is_file():
            errors.append(f"missing course-content review template: {path.relative_to(root)}")
    if errors:
        return errors

    try:
        topic, _ = parse_frontmatter(topic_path)
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    outcome_errors, outcomes = outcome_contract_errors(topic)
    errors.extend(outcome_errors)
    markers = {value.upper() for value in OUTCOME_MARKER.findall(module_path.read_text(encoding="utf-8"))}
    if set(outcomes) != markers:
        errors.append("templates/module.md outcome markers must match templates/topic.md learning_outcomes")

    rubric = _mapping(load_yaml(rubric_path))
    mapped = {
        _text(outcome_id)
        for raw_question in _list(rubric.get("questions"))
        for outcome_id in _list(_mapping(raw_question).get("outcome_ids"))
        if _text(outcome_id)
    }
    if not set(outcomes).issubset(mapped):
        errors.append("templates/assessment-rubric.yml must map every template outcome")

    review = _mapping(load_yaml(review_path))
    if _text(review.get("reviewer_role")) != "course_content_reviewer":
        errors.append("templates/content-review.yml must define course_content_reviewer")
    if _text(review.get("review_mode")) != "independent_pass":
        errors.append("templates/content-review.yml must define independent_pass")
    for check in REQUIRED_CHECKS:
        if check not in _mapping(review.get("checks")):
            errors.append(f"templates/content-review.yml is missing check: {check}")

    return errors


def validate_repository(root: Path) -> ReviewResult:
    errors = template_contract_errors(root)
    instance_path = root / ".open-study-path" / "instance.yml"
    if not instance_path.is_file():
        return ReviewResult(tuple(errors))

    instance = _mapping(load_yaml(instance_path))
    if not review_enabled(instance):
        return ReviewResult(tuple(errors))

    topics_dir = root / "study" / "topics"
    if not topics_dir.is_dir():
        return ReviewResult(tuple(errors))

    reviews_dir = root / "state" / "content-reviews"
    for topic_path in sorted(topics_dir.glob("TOPIC-*.md")):
        try:
            topic, _ = parse_frontmatter(topic_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        topic_errors, _ = outcome_contract_errors(topic)
        errors.extend(topic_errors)
        topic_id = _text(topic.get("id"))
        review_path = reviews_dir / f"{topic_id}.yml"

        if _text(topic.get("content_status")) != "materialized":
            if review_path.exists():
                errors.append(f"planned topic {topic_id} must not have an approved content review")
            continue

        module_path = root / _text(topic.get("module"))
        rubric_path = root / _text(topic.get("assessment"))
        for path in [module_path, rubric_path, review_path]:
            if not path.is_file():
                errors.append(f"materialized topic {topic_id} is missing review input: {path.relative_to(root)}")
        if not all(path.is_file() for path in [module_path, rubric_path, review_path]):
            continue

        rubric = _mapping(load_yaml(rubric_path))
        review = _mapping(load_yaml(review_path))
        result = validate_materialized_topic(
            topic,
            module_path.read_text(encoding="utf-8"),
            rubric,
            review,
        )
        errors.extend(result.errors)

    return ReviewResult(tuple(errors))
