#!/usr/bin/env python3
"""Deterministic parsing and validation of diagnostic-answer form submissions.

Etapa 9d: the diagnostic session's question batch (Etapa 9c) is answered
either by a plain issue comment or by filling in the reusable
`.github/ISSUE_TEMPLATE/diagnostic-answer.yml` form, which always creates a
*new* issue (GitHub Issue Forms cannot reply into an existing issue). This
module is the pure, offline-testable half of resolving that new issue back
to the session it answers and extracting its rendered answers -- no network
access, same "deterministic code decides identity, the model only supplies
already-verified content" split `scripts/intake_resolution.py` established
for intake.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

CURRENT_FORM_MARKER = "<!-- open-study-path:diagnostic-answer form_id=diagnostic-answer version=1 -->"
ANSWER_LABEL = "diagnostic:answer"
IMPORTED_LABEL = "diagnostic:answer-imported"
SESSION_LABEL = "diagnostic:in-progress"
MAX_ANSWER_FIELDS = 10
NO_RESPONSE_VALUES = {"", "_no response_", "no response", "n/a", "none"}

SESSION_ISSUE_HEADING = "### Número da issue da sua sessão de diagnóstico"


@dataclass(frozen=True)
class AnswerIssue:
    number: int
    title: str
    body: str
    labels: frozenset[str]
    is_pull_request: bool = False
    author_login: str | None = None


@dataclass(frozen=True)
class AnswerDecision:
    issue_number: int
    accepted: bool
    session_issue_number: int | None
    answers: tuple[str, ...]
    reasons: tuple[str, ...]


def _section_value(body: str, heading: str) -> str | None:
    pattern = re.compile(rf"(?ms)^{re.escape(heading)}\s*\n+(.*?)(?=^###\s|\Z)")
    match = pattern.search(body)
    if not match:
        return None
    return match.group(1).strip()


def extract_session_issue_number(body: str) -> int | None:
    """Parse the rendered 'session_issue_number' field. Digits only, no guessing."""

    value = _section_value(body, SESSION_ISSUE_HEADING)
    if value is None:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    return int(match.group(0))


def extract_answers(body: str, max_fields: int = MAX_ANSWER_FIELDS) -> tuple[tuple[int, str], ...]:
    """Every non-empty answer_N field, as (question_number, answer) pairs, in order.

    Skipped (empty) fields are omitted entirely rather than renumbered --
    a reply answering questions 1, 2 and 4 must still say "4.", not be
    relabeled "3.", or the diagnostic author (which only ever sees the
    reposted text, never the original field IDs) has no way to tell which
    question an answer actually responds to.
    """

    answers: list[tuple[int, str]] = []
    for index in range(1, max_fields + 1):
        heading = f"### Resposta à Pergunta {index}"
        value = _section_value(body, heading)
        if value is None:
            continue
        if value.strip().lower() in NO_RESPONSE_VALUES:
            continue
        answers.append((index, value.strip()))
    return tuple(answers)


def render_answers_as_comment(answers: Sequence[tuple[int, str]]) -> str:
    """Format extracted (question_number, answer) pairs as a plain numbered

    comment, indistinguishable from a learner who typed everything by hand
    -- this is what the diagnostic author sees via list_issue_comments, with
    no special marker. Uses each answer's real question number, not a
    resequenced count, so a skipped question does not shift every answer
    after it.
    """

    lines = [f"{number}. {answer}" for number, answer in answers]
    return "\n\n".join(lines)


def classify_answer_issue(
    issue: AnswerIssue,
    *,
    session_labels: frozenset[str] | None,
    session_lookup_failed: bool = False,
) -> AnswerDecision:
    """Classify one diagnostic-answer issue.

    `session_labels` is the labels of the referenced session issue, fetched
    by the caller (this function does no I/O) -- pass None only when the
    session issue number itself could not be parsed; pass
    `session_lookup_failed=True` when a session number was found but fetching
    that issue failed (e.g. it does not exist), to distinguish the two.
    """

    reasons: list[str] = []
    labels = {label.strip().lower() for label in issue.labels if label.strip()}

    if issue.is_pull_request:
        reasons.append("pull_request")
    if IMPORTED_LABEL in labels:
        reasons.append("already_imported")
    if ANSWER_LABEL not in labels:
        reasons.append("missing_discovery_label")

    session_issue_number = extract_session_issue_number(issue.body)
    if session_issue_number is None:
        reasons.append("missing_session_issue_number")
    elif session_lookup_failed:
        reasons.append("session_issue_not_found")
    elif session_labels is not None and SESSION_LABEL not in {
        label.strip().lower() for label in session_labels
    }:
        reasons.append("session_not_in_progress")

    answers = extract_answers(issue.body) if not reasons else ()
    if not reasons and not answers:
        reasons.append("missing_answers")

    return AnswerDecision(
        issue_number=issue.number,
        accepted=not reasons,
        session_issue_number=session_issue_number,
        answers=answers,
        reasons=tuple(reasons),
    )


def render_rejection_comment(decision: AnswerDecision) -> str:
    """Explain why a submission was not imported, for a comment on the answer issue."""

    reason_text = {
        "pull_request": "isso não é uma issue, é um pull request.",
        "already_imported": "esta submissão já foi importada antes.",
        "missing_discovery_label": (
            f"a label `{ANSWER_LABEL}` não está presente (não crie ou remova labels manualmente)."
        ),
        "missing_session_issue_number": (
            "o campo \"Número da issue da sua sessão de diagnóstico\" está vazio ou não contém um número."
        ),
        "session_issue_not_found": (
            f"a issue #{decision.session_issue_number} informada não foi encontrada neste repositório."
        ),
        "session_not_in_progress": (
            f"a issue #{decision.session_issue_number} não está com a label `{SESSION_LABEL}` "
            "(a sessão pode já ter sido concluída ou o número está errado)."
        ),
        "missing_answers": "nenhum campo de resposta (Resposta à Pergunta 1, 2, ...) foi preenchido.",
    }
    lines = [
        "Não foi possível importar esta resposta automaticamente:",
        "",
    ]
    lines.extend(f"- {reason_text.get(reason, reason)}" for reason in decision.reasons)
    lines.append("")
    lines.append(
        "Confira o número da sessão e tente enviar o formulário de novo, ou responda "
        "diretamente com um comentário na issue da sessão."
    )
    return "\n".join(lines)
