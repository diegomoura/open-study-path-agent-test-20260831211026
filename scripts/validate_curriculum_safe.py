#!/usr/bin/env python3
"""Run curriculum validation with learner-facing modules and structural placeholder detection.

Topic contracts retain operational metadata. Published lesson Markdown begins directly
with its title and learning content, without YAML frontmatter rendered by GitHub.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

import validate_curriculum as validator
from generated_instance_contract import (
    CANONICAL_LOCATOR,
    CANONICAL_MODULE_HEADINGS,
    assessment_form_text,
    heading_order_errors,
)

ROOT = Path(__file__).resolve().parents[1]

PLACEHOLDER_TOKEN = re.compile(
    r"(?:\breplace me\b|\bTOPIC-000\b|\bstudy the core concept\b|\bsubstitua por\b)",
    re.IGNORECASE,
)

PLACEHOLDER_LINES = {
    "Explique em poucas linhas o que a pessoa vai aprender, por que isso importa para o objetivo dela, quanto tempo reservar e o que produzir ao final. Este arquivo deve ser uma aula autocontida, não apenas uma lista de tarefas.",
    "Divida a experiência em três a sete ações pequenas e verificáveis. Cada ação deve normalmente durar entre 10 e 25 minutos. Os tempos são sugestões, não limites rígidos.",
    "Inclua duas ou três perguntas curtas ou tarefas de recuperação ativa. Dê orientação clara para revisar somente os pré-requisitos diretos quando necessário. Não faça perguntas que pressuponham termos ainda não explicados.",
    "Ensine efetivamente o conteúdo em linguagem adequada ao nível configurado. Inclua definições, relações entre conceitos, limites, nuances e raciocínio. Não use placeholders como “estude o conceito”.",
    "Introduza o que o diagrama representa e por que ele ajuda. Todo módulo pronto deve conter ao menos um diagrama Mermaid útil e explicado.",
    "Apresente ao menos dois exemplos resolvidos passo a passo:",
    "Liste equívocos prováveis, explique por que falham e mostre como reformular o raciocínio.",
    "Inclua exercícios com pistas graduais. Não revele imediatamente a resposta completa; mostre critérios para a pessoa conferir o próprio raciocínio.",
    "Inclua tarefas que exijam transferência para um caso novo e produção do entregável definido no tópico. A prática deve desenvolver a capacidade prometida, não apenas pedir repetição de definições.",
    "Inclua perguntas que possam ser respondidas sem olhar o texto. Para uma aula iniciante, inclua ao menos uma pergunta de definição em linguagem própria e outra que peça aplicação ou contraste.",
    "Descreva exatamente o entregável e como vincular ou transcrever a evidência no formulário. Não peça dados pessoais desnecessários.",
}

TOPIC_HEADINGS = [
    "## O que você vai aprender",
    "## Por que isso importa para você",
    "## O que você já precisa saber",
    "## Seu plano para esta etapa",
    "## Aula",
    "## Prática",
    "## O que você vai produzir",
    "## Como mostrar o que aprendeu",
    "## Para concluir esta etapa",
    "## Avaliação",
    "## Fontes principais",
]

MODULE_HEADINGS = list(CANONICAL_MODULE_HEADINGS)


def contains_template_placeholder(body: str) -> bool:
    """Return true only for durable template residue, not ordinary prose."""
    if PLACEHOLDER_TOKEN.search(body):
        return True
    normalized_lines = {line.strip() for line in body.splitlines() if line.strip()}
    return bool(normalized_lines.intersection(PLACEHOLDER_LINES))


class StructuralPlaceholderPattern:
    """Provide the minimal search interface expected by validate_curriculum."""

    @staticmethod
    def search(body: str) -> object | None:
        return object() if contains_template_placeholder(body) else None


def topic_contract(topic_id: str) -> tuple[dict[str, Any], str]:
    path = ROOT / "study" / "topics" / f"{topic_id}.md"
    return validator.parse_frontmatter(path)


def required_resource_lines(body: str, path: Path) -> list[str]:
    match = re.search(
        r"### Essenciais\s*(.*?)(?:\n### Para aprofundar|\n## Ao estudar com um assistente de IA|\Z)",
        body,
        re.DOTALL,
    )
    if not match:
        validator.fail(f"missing Essenciais resources subsection: {path.relative_to(ROOT)}")
    lines = [line.strip()[2:].strip() for line in match.group(1).splitlines() if line.strip().startswith("- ")]
    if not lines:
        validator.fail(f"must contain at least one essential resource: {path.relative_to(ROOT)}")
    return lines


_original_section = validator.section


def compatible_section(body: str, heading: str) -> str:
    aliases = {
        "## Learning activities": "## Seu plano para esta etapa",
        "## Plano de execução": "## Sua sessão de estudo",
    }
    return _original_section(body, aliases.get(heading, heading))


def check_module(topic_id: str, path: Path, config: dict[str, Any]) -> None:
    body = path.read_text(encoding="utf-8")
    if body.startswith("---\n"):
        validator.fail(f"module {topic_id} exposes YAML frontmatter to the learner")

    metadata, _ = topic_contract(topic_id)
    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        validator.fail(f"topic contract {topic_id} must define a title")
    if not re.search(rf"^#\s+(?:\d+\.\s+|{re.escape(topic_id)}\s+[—-]\s+)?{re.escape(title)}\s*$", body, re.MULTILINE):
        validator.fail(f"module {topic_id} must begin with a learner-facing title")

    hours = metadata.get("estimated_hours")
    if not isinstance(hours, (int, float)) or hours <= 0:
        validator.fail(f"topic contract {topic_id} must define positive estimated_hours")
    minutes = round(float(hours) * 60)
    if minutes > config["granularity"]["split_topic_above_minutes"]:
        validator.fail(f"module {topic_id} exceeds split threshold: {minutes} minutes")

    structure_errors = heading_order_errors(body)
    if structure_errors:
        validator.fail(f"module {topic_id} {structure_errors[0]}")

    words = re.findall(r"\b\w+\b", body, flags=re.UNICODE)
    if len(words) < 500:
        validator.fail(f"module {topic_id} is too short to be complete: {len(words)} words")
    if StructuralPlaceholderPattern.search(body):
        validator.fail(f"module {topic_id} contains template placeholder content")
    if body.count("### Exemplo") + body.count("**Exemplo") < 2:
        validator.fail(f"module {topic_id} must contain at least two worked examples")
    if body.count("```mermaid") < 1:
        validator.fail(f"module {topic_id} must contain at least one Mermaid diagram")

    validator.check_duration_items(
        topic_id,
        validator.checkbox_lines(compatible_section(body, "## Sua sessão de estudo")),
        config,
        "module plan",
    )
    if f"Terminei {title}. Avalie minhas respostas." not in body:
        validator.fail(f"module {topic_id} is missing the natural assessment command")


def check_issue_form(topic_id: str, path: Path) -> None:
    form = validator.load_yaml(path)
    if not isinstance(form, dict):
        validator.fail(f"invalid assessment Issue Form for {topic_id}")
    metadata, _ = topic_contract(topic_id)
    title = metadata.get("title")
    if topic_id not in str(form.get("name", "")) or topic_id not in str(form.get("title", "")):
        validator.fail(f"assessment Issue Form does not identify {topic_id}")
    labels = form.get("labels")
    if not isinstance(labels, list) or not {"assessment", "assessment:submitted"}.issubset(set(labels)):
        validator.fail(f"assessment Issue Form {topic_id} is missing standard labels")
    body = form.get("body")
    if not isinstance(body, list):
        validator.fail(f"assessment Issue Form body must be a list for {topic_id}")
    ids = [entry.get("id") for entry in body if isinstance(entry, dict)]
    for question_id in ["q1", "q2", "q3", "q4", "q5", "confirmation"]:
        if question_id not in ids:
            validator.fail(f"assessment Issue Form {topic_id} is missing {question_id}")

    semantic_body = assessment_form_text(form)
    if f"open-study-path:assessment topic_id={topic_id}" not in semantic_body:
        validator.fail(f"assessment Issue Form {topic_id} is missing deterministic topic marker")
    if isinstance(title, str) and f"Terminei {title}. Avalie minhas respostas." not in semantic_body:
        validator.fail(f"assessment Issue Form {topic_id} is missing the natural return command")


def main() -> None:
    validator.PLACEHOLDER_CONTENT = StructuralPlaceholderPattern()
    validator.CANONICAL_LOCATOR = CANONICAL_LOCATOR
    validator.TOPIC_HEADINGS = TOPIC_HEADINGS
    validator.MODULE_HEADINGS = MODULE_HEADINGS
    validator.required_resource_lines = required_resource_lines
    validator.section = compatible_section
    validator.check_module = check_module
    validator.check_issue_form = check_issue_form
    validator.main()


if __name__ == "__main__":
    main()
