#!/usr/bin/env python3
"""Behavioral regressions for deterministic intake resolution."""

from __future__ import annotations

from intake_resolution import CURRENT_MARKER, IntakeIssue, resolve_candidates

HEADINGS = (
    "### O que você quer aprender?",
    "### Conte um pouco mais sobre seu objetivo",
    "### Como você descreve seu nível atual?",
    "### Em qual idioma prefere estudar?",
    "### Como você prefere organizar a experiência?",
    "### Onde gostaria de acompanhar suas etapas?",
    "### Antes de enviar",
)
REQUIRED_RESPONSE_HEADINGS = (
    "### O que você quer aprender?",
    "### Como você descreve seu nível atual?",
    "### Em qual idioma prefere estudar?",
    "### Como você prefere organizar a experiência?",
    "### Onde gostaria de acompanhar suas etapas?",
)
CONSENT_HEADING = "### Antes de enviar"

BODY = """### O que você quer aprender?

Quero aprender a desenvolver aplicações com IA generativa.

### Conte um pouco mais sobre seu objetivo

_No response_

### Como você descreve seu nível atual?

Iniciante

### Em qual idioma prefere estudar?

Português (Brasil)

### Como você prefere organizar a experiência?

Quero sugestões de ferramentas quando forem úteis

### Onde gostaria de acompanhar suas etapas?

Trello

### Antes de enviar

- [x] Entendo que apenas informações necessárias ao planejamento poderão ser organizadas no meu repositório.
"""


def issue(
    number: int,
    *,
    title: str = "Engenharia de Aplicações com IA Generativa",
    body: str = BODY,
    labels: tuple[str, ...] = ("study-request",),
    is_pull_request: bool = False,
    source_reference: str | None = None,
    author_login: str | None = "diegomoura",
) -> IntakeIssue:
    return IntakeIssue(
        number=number,
        title=title,
        body=body,
        labels=frozenset(labels),
        is_pull_request=is_pull_request,
        source_reference=source_reference,
        author_login=author_login,
    )


def assert_state(expected: str, *issues: IntakeIssue, imported: tuple[str, ...] = ()):
    result = resolve_candidates(
        issues,
        HEADINGS,
        imported,
        required_response_headings=REQUIRED_RESPONSE_HEADINGS,
        consent_heading=CONSENT_HEADING,
        allowed_authors=("diegomoura",),
    )
    if result.state != expected:
        raise SystemExit(f"expected {expected}, got {result.state}: {result}")
    return result


def main() -> None:
    # This is the body shape GitHub actually renders from an Issue Form. The
    # markdown-only form marker is intentionally absent.
    current = issue(1)
    resolved = assert_state("unique", current)
    if resolved.accepted[0].mode != "current_form_contract":
        raise SystemExit("rendered version 4 issue was not classified from the form contract")
    if resolved.accepted[0].repairs:
        raise SystemExit(f"valid current candidate unexpectedly needs repairs: {resolved.accepted[0].repairs}")

    # A marker manually inserted into the issue body is ignored; it is not an
    # identity requirement and does not replace the other checks.
    manually_marked = issue(2, body=f"{CURRENT_MARKER}\n\n{BODY}")
    assert_state("unique", manually_marked)

    missing_title = issue(3, title="")
    assert_state("none", missing_title)

    missing_label = issue(4, labels=())
    rejected = assert_state("none", missing_label)
    if "missing_discovery_label" not in rejected.rejected[0].reasons:
        raise SystemExit("missing automatic discovery label was not rejected")

    headings_only = issue(
        5,
        body="\n\n".join(f"{heading}\n\n_No response_" for heading in HEADINGS),
    )
    assert_state("none", headings_only)

    unchecked_consent = issue(
        6,
        body=BODY.replace("- [x] Entendo", "- [ ] Entendo"),
    )
    rejected = assert_state("none", unchecked_consent)
    if "missing_checked_consent" not in rejected.rejected[0].reasons:
        raise SystemExit("unchecked consent was not rejected")

    imported_label = issue(7, labels=("study-request", "intake:imported"))
    assert_state("none", imported_label)

    pull_request = issue(8, is_pull_request=True)
    assert_state("none", pull_request)

    missing_heading = issue(
        9,
        body=BODY.replace("### Em qual idioma prefere estudar?", "### Idioma removido"),
    )
    assert_state("none", missing_heading)

    unexpected_author = issue(10, author_login="outra-pessoa")
    rejected = assert_state("none", unexpected_author)
    if "unexpected_author" not in rejected.rejected[0].reasons:
        raise SystemExit("unexpected author was not rejected")

    first = issue(11)
    second = issue(12)
    assert_state("ambiguous", first, second)

    recorded = issue(13, source_reference="github_issue:13")
    assert_state("none", recorded, imported=("github_issue:13",))

    print("Deterministic rendered-intake resolution regressions passed.")


if __name__ == "__main__":
    main()
