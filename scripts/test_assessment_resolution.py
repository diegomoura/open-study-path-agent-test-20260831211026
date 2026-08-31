#!/usr/bin/env python3
"""Behavioral regressions for deterministic assessment resolution."""

from __future__ import annotations

from assessment_resolution import (
    AssessmentIssue,
    normalized_title,
    resolve_candidates,
    title_needs_normalization,
    topic_marker,
)

TOPIC_ID = "TOPIC-002"
TOPIC_TITLE = "Tipos, tipagem estática e erros"
MARKER = topic_marker(TOPIC_ID)


def issue(
    number: int,
    *,
    title: str = "[Avaliação] TOPIC-002 — Tipos, tipagem estática e erros",
    labels: tuple[str, ...] = ("assessment", "assessment:submitted"),
    body: str | None = None,
    created_at: str = "2026-08-19T12:00:00Z",
    is_pull_request: bool = False,
    author_login: str | None = "aprendiz",
) -> AssessmentIssue:
    return AssessmentIssue(
        number=number,
        title=title,
        body=body if body is not None else f"Minhas respostas.\n\n<!-- {MARKER} -->",
        labels=frozenset(labels),
        created_at=created_at,
        is_pull_request=is_pull_request,
        author_login=author_login,
    )


def assert_state(expected: str, *issues: AssessmentIssue, **kwargs):
    resolved = resolve_candidates(issues, TOPIC_ID, **kwargs)
    if resolved.state != expected:
        raise SystemExit(
            f"expected state {expected!r}, got {resolved.state!r} "
            f"(accepted={resolved.accepted}, rejected={resolved.rejected})"
        )
    return resolved


def main() -> None:
    valid = issue(1)
    resolved = assert_state("unique", valid)
    if resolved.accepted[0].issue_number != 1:
        raise SystemExit("unique candidate resolved to the wrong issue number")

    # Never choose an arbitrary newest issue: with zero valid candidates the
    # state must be "none", not a guess at the highest issue number.
    missing_label = issue(2, labels=("assessment",))  # no assessment:submitted
    rejected = assert_state("none", missing_label)
    if "missing_submitted_label" not in rejected.rejected[0].reasons:
        raise SystemExit("missing assessment:submitted was not rejected")

    missing_assessment_label = issue(3, labels=("assessment:submitted",))
    rejected = assert_state("none", missing_assessment_label)
    if "missing_assessment_label" not in rejected.rejected[0].reasons:
        raise SystemExit("missing assessment label was not rejected")

    wrong_topic_marker = issue(4, body="Minhas respostas.\n\n<!-- open-study-path:assessment topic_id=TOPIC-999 -->")
    rejected = assert_state("none", wrong_topic_marker)
    if "missing_topic_marker" not in rejected.rejected[0].reasons:
        raise SystemExit("wrong topic marker was not rejected")

    # Title is a "preferred consistency signal", never a rejection reason --
    # an edited title must still resolve if the marker/labels are correct.
    edited_title = issue(5, title="respostas da aula 2!!")
    assert_state("unique", edited_title)

    already_graded = issue(6, labels=("assessment", "assessment:submitted", "assessment:graded"))
    rejected = assert_state("none", already_graded)
    if "already_graded" not in rejected.rejected[0].reasons:
        raise SystemExit("assessment:graded issue was not rejected")

    already_recorded = issue(7)
    rejected = assert_state("none", already_recorded, recorded_issue_numbers=(7,))
    if "already_recorded_attempt" not in rejected.rejected[0].reasons:
        raise SystemExit("already-recorded attempt issue was not rejected")

    # Rule 6: a resubmission must be created after the last recorded attempt,
    # not merely be a different issue number.
    stale_resubmission = issue(8, created_at="2026-08-10T12:00:00Z")
    rejected = assert_state(
        "none", stale_resubmission, last_attempt_created_at="2026-08-15T00:00:00Z"
    )
    if "not_created_after_last_attempt" not in rejected.rejected[0].reasons:
        raise SystemExit("resubmission created before the last attempt was not rejected")

    fresh_resubmission = issue(9, created_at="2026-08-20T00:00:00Z")
    assert_state("unique", fresh_resubmission, last_attempt_created_at="2026-08-15T00:00:00Z")

    pull_request = issue(10, is_pull_request=True)
    assert_state("none", pull_request)

    unexpected_author = issue(11, author_login="outra-pessoa")
    rejected = assert_state("none", unexpected_author, allowed_authors=("aprendiz",))
    if "unexpected_author" not in rejected.rejected[0].reasons:
        raise SystemExit("unexpected author was not rejected")

    first = issue(12)
    second = issue(13)
    assert_state("ambiguous", first, second)

    if not title_needs_normalization("respostas da aula 2!!", TOPIC_ID, TOPIC_TITLE):
        raise SystemExit("edited title should be reported as needing normalization")
    normalized = normalized_title(TOPIC_ID, TOPIC_TITLE)
    if title_needs_normalization(normalized, TOPIC_ID, TOPIC_TITLE):
        raise SystemExit("already-normalized title should not need normalization again")

    print("Deterministic assessment resolution regressions passed.")


if __name__ == "__main__":
    main()
