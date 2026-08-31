#!/usr/bin/env python3
"""Deterministic GitHub Issue Form intake resolution.

The repository's current Issue Form contract identifies the supported version.
A submitted issue is identified from GitHub-generated signals and its rendered
field structure; markdown blocks from the form are not expected in the issue
body.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

CURRENT_FORM_ID = "create-study-path"
CURRENT_FORM_VERSION = 4
CURRENT_MARKER = (
    "<!-- open-study-path:intake "
    f"form_id={CURRENT_FORM_ID} version={CURRENT_FORM_VERSION} -->"
)
DISCOVERY_LABEL = "study-request"
IMPORTED_LABEL = "intake:imported"
NO_RESPONSE_VALUES = {"", "_no response_", "no response", "n/a", "none"}


@dataclass(frozen=True)
class IntakeIssue:
    number: int
    title: str
    body: str
    labels: frozenset[str]
    is_pull_request: bool = False
    source_reference: str | None = None
    author_login: str | None = None


@dataclass(frozen=True)
class CandidateDecision:
    issue_number: int
    accepted: bool
    mode: str | None
    reasons: tuple[str, ...]
    repairs: tuple[str, ...]


@dataclass(frozen=True)
class Resolution:
    state: str
    accepted: tuple[CandidateDecision, ...]
    rejected: tuple[CandidateDecision, ...]


def _normalized_labels(labels: Iterable[str]) -> set[str]:
    return {label.strip().lower() for label in labels if label.strip()}


def _has_expected_headings(body: str, expected_headings: Sequence[str]) -> bool:
    return bool(expected_headings) and all(heading in body for heading in expected_headings)


def _has_course_title(title: str) -> bool:
    return bool(title.strip())


def _section_value(body: str, heading: str) -> str | None:
    """Return the rendered Markdown content for one Issue Form heading."""

    pattern = re.compile(
        rf"(?ms)^{re.escape(heading)}\s*\n+(.*?)(?=^###\s|\Z)"
    )
    match = pattern.search(body)
    if not match:
        return None
    return match.group(1).strip()


def _has_required_response(body: str, heading: str) -> bool:
    value = _section_value(body, heading)
    if value is None:
        return False
    return value.strip().lower() not in NO_RESPONSE_VALUES


def _has_checked_consent(body: str, consent_heading: str) -> bool:
    value = _section_value(body, consent_heading)
    if value is None:
        return False
    return bool(re.search(r"(?mi)^\s*-\s*\[x\]\s+\S", value))


def classify_issue(
    issue: IntakeIssue,
    expected_headings: Sequence[str],
    imported_references: Iterable[str] = (),
    *,
    required_response_headings: Sequence[str] = (),
    consent_heading: str | None = None,
    allowed_authors: Iterable[str] = (),
) -> CandidateDecision:
    """Classify one issue without selecting it.

    The current form version is established by the repository configuration and
    the checked-in Issue Form, not by a hidden comment in the rendered issue.
    """

    reasons: list[str] = []
    labels = _normalized_labels(issue.labels)
    imported = {reference for reference in imported_references if reference}
    normalized_allowed_authors = {
        login.strip().lower() for login in allowed_authors if login and login.strip()
    }

    if issue.is_pull_request:
        reasons.append("pull_request")
    if issue.source_reference and issue.source_reference in imported:
        reasons.append("already_recorded")
    if IMPORTED_LABEL in labels:
        reasons.append("already_labeled_imported")
    if DISCOVERY_LABEL not in labels:
        reasons.append("missing_discovery_label")
    if not _has_expected_headings(issue.body, expected_headings):
        reasons.append("missing_expected_headings")
    if not _has_course_title(issue.title):
        reasons.append("missing_course_title")

    for heading in required_response_headings:
        if not _has_required_response(issue.body, heading):
            reasons.append(f"missing_required_response:{heading}")

    if consent_heading and not _has_checked_consent(issue.body, consent_heading):
        reasons.append("missing_checked_consent")

    if normalized_allowed_authors:
        author = (issue.author_login or "").strip().lower()
        if author not in normalized_allowed_authors:
            reasons.append("unexpected_author")

    if reasons:
        return CandidateDecision(issue.number, False, None, tuple(reasons), ())

    return CandidateDecision(
        issue.number,
        True,
        "current_form_contract",
        (),
        (),
    )


def resolve_candidates(
    issues: Iterable[IntakeIssue],
    expected_headings: Sequence[str],
    imported_references: Iterable[str] = (),
    *,
    required_response_headings: Sequence[str] = (),
    consent_heading: str | None = None,
    allowed_authors: Iterable[str] = (),
) -> Resolution:
    accepted: list[CandidateDecision] = []
    rejected: list[CandidateDecision] = []

    for issue in issues:
        decision = classify_issue(
            issue,
            expected_headings,
            imported_references,
            required_response_headings=required_response_headings,
            consent_heading=consent_heading,
            allowed_authors=allowed_authors,
        )
        (accepted if decision.accepted else rejected).append(decision)

    state = "unique" if len(accepted) == 1 else "none" if not accepted else "ambiguous"
    return Resolution(state, tuple(accepted), tuple(rejected))
