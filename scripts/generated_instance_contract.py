#!/usr/bin/env python3
"""Shared invariants for complete generated study bundles.

Keep learner-facing lesson structure, source locators, assessment semantics,
specialized review paths and regeneration closure in one importable contract.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable

CANONICAL_MODULE_HEADINGS = (
    "## Antes de começar",
    "## Sua sessão de estudo",
    "## O que você vai aprender",
    "## Começando do zero",
    "## Intuição antes dos detalhes",
    "## Recupere o que já sabe",
    "## Conteúdo essencial",
    "## Mapa visual",
    "## Exemplos trabalhados",
    "## Erros comuns e como corrigir",
    "## Prática guiada",
    "## Prática independente",
    "## Outras formas de aprender",
    "## Confira sem consultar",
    "## O que você vai produzir",
    "## Avaliação",
    "## Como este conteúdo foi construído",
    "## Fontes e caminhos para aprofundar",
)

OTHER_FORMATS_HEADING = "## Outras formas de aprender"

SPECIALIZED_REVIEW_PREFIXES = (
    "state/content-reviews/",
)

# A precise URL or DOI is already a durable locator. Section, page and numbered
# locators remain accepted for non-addressable books and documents.
CANONICAL_LOCATOR = re.compile(
    r"(?:https?://[^\s)>]+|\bdoi\s*:\s*10\.\d{4,9}/[-._;()/:a-z0-9]+|"
    r"\b10\.\d{4,9}/[-._;()/:a-z0-9]+|§|\b\d+\b|\b[IVXLCDM]+\.)",
    re.IGNORECASE,
)


def normalize_path(value: str) -> str:
    normalized = Path(value).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_specialized_review_path(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized.endswith((".yml", ".yaml")) and normalized.startswith(
        SPECIALIZED_REVIEW_PREFIXES
    )


def heading_order_errors(
    body: str,
    headings: Iterable[str] = CANONICAL_MODULE_HEADINGS,
) -> tuple[str, ...]:
    """Return missing or out-of-order canonical lesson headings."""

    errors: list[str] = []
    previous = -1
    for heading in headings:
        position = body.find(heading)
        if position < 0:
            errors.append(f"missing heading: {heading}")
            continue
        if position <= previous:
            errors.append(f"heading is out of canonical order: {heading}")
        previous = max(previous, position)
    return tuple(errors)


def semantic_text(value: Any) -> str:
    """Flatten parsed YAML/JSON values without depending on serializer wrapping."""

    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(semantic_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(semantic_text(item) for item in value)
    return ""


def assessment_form_text(form: Any) -> str:
    if not isinstance(form, dict):
        return ""
    return semantic_text(form.get("body", []))


def regeneration_targets(changed_paths: Iterable[str]) -> tuple[str, ...]:
    """Return dependent artifacts that must be refreshed in the same final batch.

    The result is advisory for authoring orchestration; validators remain the
    source of truth for exact PDF provenance and review fingerprints.
    """

    targets: set[str] = set()
    for raw in changed_paths:
        path = normalize_path(raw)
        match = re.fullmatch(r"study/modules/(TOPIC-\d+)\.md", path)
        if match:
            topic = match.group(1)
            targets.update(
                {
                    f"state/content-reviews/{topic}.yml",
                }
            )
            continue
    return tuple(sorted(targets))
