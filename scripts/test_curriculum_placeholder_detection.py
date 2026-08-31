#!/usr/bin/env python3
"""Regression tests for curriculum and complete generated-bundle contracts."""

from __future__ import annotations

from pathlib import Path

import yaml

from generated_instance_contract import (
    CANONICAL_LOCATOR,
    CANONICAL_MODULE_HEADINGS,
    OTHER_FORMATS_HEADING,
    assessment_form_text,
    heading_order_errors,
    is_specialized_review_path,
    regeneration_targets,
)
from validate_curriculum_safe import MODULE_HEADINGS, contains_template_placeholder

ROOT = Path(__file__).resolve().parents[1]


def assert_placeholder(text: str) -> None:
    if not contains_template_placeholder(text):
        raise SystemExit(f"expected placeholder was accepted: {text!r}")


def assert_legitimate(text: str) -> None:
    if contains_template_placeholder(text):
        raise SystemExit(f"legitimate teaching prose was rejected: {text!r}")


def test_source_locators() -> None:
    assert CANONICAL_LOCATOR.search("https://www.pomodorotechnique.com/")
    assert CANONICAL_LOCATOR.search("DOI: 10.1000/example")
    assert CANONICAL_LOCATOR.search("10.5555/abc.def")
    assert CANONICAL_LOCATOR.search("§ 2")


def test_one_ordered_lesson_vocabulary() -> None:
    assert tuple(MODULE_HEADINGS) == CANONICAL_MODULE_HEADINGS
    valid = "\n\n".join(CANONICAL_MODULE_HEADINGS)
    assert heading_order_errors(valid) == ()

    wrong = valid.replace(
        "## Começando do zero\n\n## Intuição antes dos detalhes",
        "## Intuição antes dos detalhes\n\n## Começando do zero",
    )
    assert any("out of canonical order" in error for error in heading_order_errors(wrong))


def test_assessment_commands_are_semantic() -> None:
    command = "Terminei Uma aula com um título suficientemente longo para o YAML quebrar a linha. Avalie minhas respostas."
    form = {
        "body": [
            {
                "type": "markdown",
                "attributes": {
                    "value": (
                        "<!-- open-study-path:assessment topic_id=TOPIC-001 -->\n"
                        + command
                    )
                },
            }
        ]
    }
    serialized = yaml.safe_dump(form, sort_keys=False, allow_unicode=True, width=40)
    parsed = yaml.safe_load(serialized)
    assert command in assessment_form_text(parsed)


def test_specialized_reviews_do_not_need_second_review() -> None:
    assert is_specialized_review_path("state/content-reviews/TOPIC-001.yml")
    assert not is_specialized_review_path("state/reviews/curriculum.yml")


def test_lesson_practice_precedes_alternative_formats() -> None:
    template = (ROOT / "templates/module.md").read_text(encoding="utf-8")
    assert template.index("## Prática guiada") < template.index("## Prática independente")
    assert template.index("## Prática independente") < template.index(OTHER_FORMATS_HEADING)
    assert "Quizlet" not in template
    assert ".tsv" not in template.lower()


def test_regeneration_closure() -> None:
    targets = set(regeneration_targets(["study/modules/TOPIC-001.md"]))
    assert targets == {
        "state/content-reviews/TOPIC-001.yml",
    }


def test_finalization_contract_is_wired() -> None:
    manifest = yaml.safe_load((ROOT / "instructions/manifest.yml").read_text(encoding="utf-8"))
    phases = {phase["id"]: phase for phase in manifest["phases"]}
    expected = "instructions/38-finalize-generated-bundle.md"
    assert phases["generate"]["finalization_contract"] == expected
    assert phases["evaluate"]["internal_bundle_finalization"] == expected
    assert (ROOT / expected).is_file()


def main() -> None:
    assert_placeholder("# TOPIC-000 — Replace me")
    assert_placeholder(
        "Explique em poucas linhas o que a pessoa vai aprender, por que isso importa para o objetivo dela, "
        "quanto tempo reservar e o que produzir ao final. Este arquivo deve ser uma aula autocontida, "
        "não apenas uma lista de tarefas."
    )

    assert_legitimate("Descreva o impacto de um julgamento precipitado sobre a decisão seguinte.")
    assert_legitimate("Inclua exercícios adicionais somente quando ajudarem a comparar duas interpretações.")
    assert_legitimate("Apresente ao menos uma objeção real antes de formular sua resposta.")
    assert_legitimate("O estudante deve descrever o próprio raciocínio sem copiar definições.")

    test_source_locators()
    test_one_ordered_lesson_vocabulary()
    test_assessment_commands_are_semantic()
    test_specialized_reviews_do_not_need_second_review()
    test_lesson_practice_precedes_alternative_formats()
    test_regeneration_closure()
    test_finalization_contract_is_wired()

    print("Curriculum and generated-bundle regression tests passed.")


if __name__ == "__main__":
    main()
