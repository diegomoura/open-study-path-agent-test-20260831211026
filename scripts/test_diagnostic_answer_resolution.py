#!/usr/bin/env python3
"""Offline regressions for scripts/diagnostic_answer_resolution.py."""

from __future__ import annotations

from diagnostic_answer_resolution import (
    ANSWER_LABEL,
    IMPORTED_LABEL,
    SESSION_LABEL,
    AnswerIssue,
    classify_answer_issue,
    extract_answers,
    extract_session_issue_number,
    render_answers_as_comment,
    render_rejection_comment,
)

RENDERED_BODY = """### Número da issue da sua sessão de diagnóstico

7

### Resposta à Pergunta 1

Nunca li os textos originais.

### Resposta à Pergunta 2

_No response_

### Resposta à Pergunta 3

Aceitaria o que não pode controlar e focaria no que pode.
"""


def test_extract_session_issue_number_parses_digits() -> None:
    assert extract_session_issue_number(RENDERED_BODY) == 7


def test_extract_session_issue_number_handles_missing_field() -> None:
    assert extract_session_issue_number("no relevant heading here") is None


def test_extract_answers_skips_no_response_and_preserves_order() -> None:
    answers = extract_answers(RENDERED_BODY)
    assert answers == (
        (1, "Nunca li os textos originais."),
        (3, "Aceitaria o que não pode controlar e focaria no que pode."),
    )


def test_render_answers_as_comment_is_plain_numbered_list() -> None:
    text = render_answers_as_comment([(1, "primeira resposta"), (2, "segunda resposta")])
    assert text == "1. primeira resposta\n\n2. segunda resposta"


def test_render_answers_as_comment_preserves_original_question_numbers() -> None:
    # Answering questions 1 and 4 (2 and 3 skipped) must keep saying "1."
    # and "4." -- resequencing to "1."/"2." would make the diagnostic
    # author think answer "2" responds to a question that was never asked.
    text = render_answers_as_comment([(1, "resposta um"), (4, "resposta quatro")])
    assert text == "1. resposta um\n\n4. resposta quatro"


def test_classify_accepts_well_formed_submission() -> None:
    issue = AnswerIssue(
        number=9,
        title="Responder diagnóstico",
        body=RENDERED_BODY,
        labels=frozenset({ANSWER_LABEL}),
        author_login="learner",
    )
    decision = classify_answer_issue(issue, session_labels=frozenset({SESSION_LABEL}))
    assert decision.accepted
    assert decision.session_issue_number == 7
    assert len(decision.answers) == 2


def test_classify_rejects_pull_request() -> None:
    issue = AnswerIssue(
        number=9,
        title="x",
        body=RENDERED_BODY,
        labels=frozenset({ANSWER_LABEL}),
        is_pull_request=True,
    )
    decision = classify_answer_issue(issue, session_labels=frozenset({SESSION_LABEL}))
    assert not decision.accepted
    assert "pull_request" in decision.reasons


def test_classify_rejects_already_imported() -> None:
    issue = AnswerIssue(
        number=9,
        title="x",
        body=RENDERED_BODY,
        labels=frozenset({ANSWER_LABEL, IMPORTED_LABEL}),
    )
    decision = classify_answer_issue(issue, session_labels=frozenset({SESSION_LABEL}))
    assert not decision.accepted
    assert "already_imported" in decision.reasons


def test_classify_rejects_missing_discovery_label() -> None:
    issue = AnswerIssue(number=9, title="x", body=RENDERED_BODY, labels=frozenset())
    decision = classify_answer_issue(issue, session_labels=frozenset({SESSION_LABEL}))
    assert not decision.accepted
    assert "missing_discovery_label" in decision.reasons


def test_classify_rejects_missing_session_issue_number() -> None:
    body = "### Resposta à Pergunta 1\n\nalguma resposta\n"
    issue = AnswerIssue(number=9, title="x", body=body, labels=frozenset({ANSWER_LABEL}))
    decision = classify_answer_issue(issue, session_labels=None)
    assert not decision.accepted
    assert "missing_session_issue_number" in decision.reasons


def test_classify_rejects_session_not_found() -> None:
    issue = AnswerIssue(number=9, title="x", body=RENDERED_BODY, labels=frozenset({ANSWER_LABEL}))
    decision = classify_answer_issue(issue, session_labels=None, session_lookup_failed=True)
    assert not decision.accepted
    assert "session_issue_not_found" in decision.reasons


def test_classify_rejects_session_not_in_progress() -> None:
    issue = AnswerIssue(number=9, title="x", body=RENDERED_BODY, labels=frozenset({ANSWER_LABEL}))
    decision = classify_answer_issue(issue, session_labels=frozenset({"some-other-label"}))
    assert not decision.accepted
    assert "session_not_in_progress" in decision.reasons


def test_classify_rejects_no_answers_at_all() -> None:
    body = "### Número da issue da sua sessão de diagnóstico\n\n7\n"
    issue = AnswerIssue(number=9, title="x", body=body, labels=frozenset({ANSWER_LABEL}))
    decision = classify_answer_issue(issue, session_labels=frozenset({SESSION_LABEL}))
    assert not decision.accepted
    assert "missing_answers" in decision.reasons


def test_render_rejection_comment_lists_every_reason() -> None:
    issue = AnswerIssue(number=9, title="x", body=RENDERED_BODY, labels=frozenset())
    decision = classify_answer_issue(issue, session_labels=None, session_lookup_failed=True)
    text = render_rejection_comment(decision)
    assert "missing_discovery_label" not in text  # human-readable, not raw codes
    assert "diagnostic:answer" in text
    assert "#7" in text


def main() -> None:
    tests = [
        test_extract_session_issue_number_parses_digits,
        test_extract_session_issue_number_handles_missing_field,
        test_extract_answers_skips_no_response_and_preserves_order,
        test_render_answers_as_comment_is_plain_numbered_list,
        test_render_answers_as_comment_preserves_original_question_numbers,
        test_classify_accepts_well_formed_submission,
        test_classify_rejects_pull_request,
        test_classify_rejects_already_imported,
        test_classify_rejects_missing_discovery_label,
        test_classify_rejects_missing_session_issue_number,
        test_classify_rejects_session_not_found,
        test_classify_rejects_session_not_in_progress,
        test_classify_rejects_no_answers_at_all,
        test_render_rejection_comment_lists_every_reason,
    ]
    for test in tests:
        test()
    print(f"Diagnostic answer resolution regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
