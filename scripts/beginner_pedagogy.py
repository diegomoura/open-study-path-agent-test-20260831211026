#!/usr/bin/env python3
"""Reusable checks for progressive, beginner-first lesson writing."""

from __future__ import annotations

import re

from generated_instance_contract import CANONICAL_MODULE_HEADINGS, heading_order_errors

TITLE_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,7}s?\b")
EXCLUDED_TITLE_ACRONYMS = {"TOPIC"}
BEGINNER_LEVELS = {"none", "beginner", "iniciante"}


def normalize_acronym(value: str) -> str:
    """Normalize a plural acronym such as LLMs or APIs to its base form."""

    if value.endswith("s") and len(value) > 2 and value[:-1].isupper():
        return value[:-1]
    return value


def title_acronyms(title: str) -> list[str]:
    """Return distinct acronyms that a beginner should see defined."""

    found: list[str] = []
    for raw in TITLE_ACRONYM.findall(title):
        acronym = normalize_acronym(raw)
        if acronym in EXCLUDED_TITLE_ACRONYMS or acronym in found:
            continue
        found.append(acronym)
    return found


def markdown_section(body: str, heading: str) -> str:
    """Return a level-two Markdown section body or an empty string."""

    marker = f"## {heading}"
    if marker not in body:
        return ""
    remainder = body.split(marker, 1)[1]
    return remainder.split("\n## ", 1)[0]


def validate_module_pedagogy(title: str, body: str, difficulty: str) -> list[str]:
    """Return learner-experience errors without performing I/O."""

    errors: list[str] = []
    normalized_level = difficulty.strip().lower()
    beginner = normalized_level in BEGINNER_LEVELS

    has_analogy = "**Analogia:**" in body
    has_concrete_example = "**Exemplo concreto:**" in body
    if not has_analogy and not has_concrete_example:
        errors.append("needs a labeled analogy or concrete example")

    if has_analogy:
        if "**Onde a analogia ajuda:**" not in body:
            errors.append("analogy must explain where it helps")
        if "**Onde a analogia deixa de funcionar:**" not in body:
            errors.append("analogy must explain where it stops working")

    if not beginner:
        return errors

    for heading in ["Começando do zero", "Intuição antes dos detalhes"]:
        if f"## {heading}" not in body:
            errors.append(f"beginner lesson is missing: ## {heading}")

    foundation = markdown_section(body, "Começando do zero")
    if "### Vocabulário desta aula" not in foundation:
        errors.append("beginner lesson is missing: ### Vocabulário desta aula")
        vocabulary = ""
    else:
        vocabulary = foundation.split("### Vocabulário desta aula", 1)[1]

    if len(foundation.strip()) < 300:
        errors.append("beginner foundation is too brief to establish first principles")

    for acronym in title_acronyms(title):
        if not re.search(rf"\*\*{re.escape(acronym)}(?:s)?(?:\s|—|-|:)", vocabulary):
            errors.append(f"title acronym is not defined in beginner vocabulary: {acronym}")

    # The canonical sequence is shared with the curriculum validator. Limit the
    # check to the beginner foundation slice so optional later sections cannot
    # create a second, contradictory vocabulary of headings.
    first_principles = (
        "## Começando do zero",
        "## Intuição antes dos detalhes",
        "## Recupere o que já sabe",
        "## Conteúdo essencial",
    )
    for error in heading_order_errors(body, first_principles):
        if "out of canonical order" in error:
            errors.append("beginner foundation and intuition must appear before technical content")
            break

    # Keep the import live and explicit: a template change must update the same
    # ordered contract consumed by both validators.
    assert "## Começando do zero" in CANONICAL_MODULE_HEADINGS
    assert "## Conteúdo essencial" in CANONICAL_MODULE_HEADINGS

    return errors
