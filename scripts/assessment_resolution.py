#!/usr/bin/env python3
"""Deterministic assessment-issue resolution.

Mirrors scripts/intake_resolution.py's shape and purpose: instructions/
55-evaluate-topic.md's "Resolve the assessment issue" section specifies an
exact algorithm ("Never choose an arbitrary newest repository issue") and
this module makes that algorithm structural -- the model supplies inputs it
can only get by reading the repository (existing attempt files, the last
attempt's timestamp), never the classification decision itself.

Etapa 6c (docs/claude-agent-pilot-etapa6-design.md, section 5.1) scopes this
to the *primary* submission command ("Finalizei o TOPIC-000. Avalie minhas
respostas.") only. The recovery-issue variant ("RECOVERY-TOPIC-000-A<n>")
described in 55-evaluate-topic.md's "Recovery and focused reassessment"
section is a distinct resolution shape (a recovery marker plus an
unresolved-recovery-status check, not a fresh topic_id marker) and is left
for a later etapa rather than folded in here as a guessed extension.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Iterable

ASSESSMENT_LABEL = "assessment"
SUBMITTED_LABEL = "assessment:submitted"
GRADED_LABEL = "assessment:graded"
TITLE_PREFIX = "[Avaliação]"


@dataclass(frozen=True)
class AssessmentIssue:
    number: int
    title: str
    body: str
    labels: frozenset[str]
    created_at: str | None = None
    is_pull_request: bool = False
    author_login: str | None = None


@dataclass(frozen=True)
class CandidateDecision:
    issue_number: int
    accepted: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Resolution:
    state: str
    accepted: tuple[CandidateDecision, ...]
    rejected: tuple[CandidateDecision, ...]


def _normalized_labels(labels: Iterable[str]) -> set[str]:
    return {label.strip().lower() for label in labels if label.strip()}


def topic_marker(topic_id: str) -> str:
    return f"open-study-path:assessment topic_id={topic_id}"


def _has_topic_marker(body: str, topic_id: str) -> bool:
    return topic_marker(topic_id) in body


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def classify_issue(
    issue: AssessmentIssue,
    topic_id: str,
    *,
    recorded_issue_numbers: Iterable[int] = (),
    last_attempt_created_at: str | None = None,
    allowed_authors: Iterable[str] = (),
) -> CandidateDecision:
    """Classify one issue without selecting it.

    Rule numbering follows instructions/55-evaluate-topic.md's "Resolve the
    assessment issue" list exactly (1-6), so a diff against that section
    stays easy to audit.
    """

    reasons: list[str] = []
    labels = _normalized_labels(issue.labels)
    recorded = set(recorded_issue_numbers)
    normalized_allowed_authors = {
        login.strip().lower() for login in allowed_authors if login and login.strip()
    }

    if issue.is_pull_request:
        reasons.append("pull_request")
    if ASSESSMENT_LABEL not in labels:  # rule 1
        reasons.append("missing_assessment_label")
    if SUBMITTED_LABEL not in labels:  # rule 2
        reasons.append("missing_submitted_label")
    if not _has_topic_marker(issue.body, topic_id):  # rule 3
        reasons.append("missing_topic_marker")
    if issue.number in recorded:  # rule 4
        reasons.append("already_recorded_attempt")
    if GRADED_LABEL in labels:  # rule 5
        reasons.append("already_graded")

    last_attempt_at = _parse_timestamp(last_attempt_created_at)  # rule 6
    issue_created_at = _parse_timestamp(issue.created_at)
    if last_attempt_at is not None:
        if issue_created_at is None or issue_created_at <= last_attempt_at:
            reasons.append("not_created_after_last_attempt")

    if normalized_allowed_authors:
        author = (issue.author_login or "").strip().lower()
        if author not in normalized_allowed_authors:
            reasons.append("unexpected_author")

    return CandidateDecision(issue.number, not reasons, tuple(reasons))


def resolve_candidates(
    issues: Iterable[AssessmentIssue],
    topic_id: str,
    *,
    recorded_issue_numbers: Iterable[int] = (),
    last_attempt_created_at: str | None = None,
    allowed_authors: Iterable[str] = (),
) -> Resolution:
    accepted: list[CandidateDecision] = []
    rejected: list[CandidateDecision] = []

    for issue in issues:
        decision = classify_issue(
            issue,
            topic_id,
            recorded_issue_numbers=recorded_issue_numbers,
            last_attempt_created_at=last_attempt_created_at,
            allowed_authors=allowed_authors,
        )
        (accepted if decision.accepted else rejected).append(decision)

    state = "unique" if len(accepted) == 1 else "none" if not accepted else "ambiguous"
    return Resolution(state, tuple(accepted), tuple(rejected))


def normalized_title(topic_id: str, topic_title: str) -> str:
    """The repository-hygiene title normalization the instruction asks for.

    Not an acceptance criterion -- callers apply this only after resolving
    exactly one candidate, and never reject a submission for title drift.
    """

    return f"{TITLE_PREFIX} {topic_id} — {topic_title}"


def title_needs_normalization(current_title: str, topic_id: str, topic_title: str) -> bool:
    return current_title.strip() != normalized_title(topic_id, topic_title)
