#!/usr/bin/env python3
"""Validate lifecycle structure, human-facing language, visuals and sourced lessons."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

from lifecycle_next_action import PUBLISH_COMMAND, resolve_next_action

ROOT = Path(__file__).resolve().parents[1]
INSTANCE = ROOT / ".open-study-path/instance.yml"
MERMAID = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
LINK = re.compile(r"https?://[^\s)>]+")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: str | Path) -> str:
    target = ROOT / path if isinstance(path, str) else path
    if not target.is_file():
        fail(f"missing lifecycle file: {target.relative_to(ROOT)}")
    return target.read_text(encoding="utf-8")


def load_yaml(path: str) -> Any:
    return yaml.safe_load(read(path))


def require(path: str, terms: list[str]) -> None:
    content = read(path)
    for term in terms:
        if term not in content:
            fail(f"{path} is missing required term: {term}")


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    content = read(path)
    if not content.startswith("---\n"):
        fail(f"missing frontmatter: {path.relative_to(ROOT)}")
    try:
        _, raw, body = content.split("---", 2)
    except ValueError:
        fail(f"malformed frontmatter: {path.relative_to(ROOT)}")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        fail(f"frontmatter must be an object: {path.relative_to(ROOT)}")
    return data, body


def validate_manifest() -> None:
    manifest = load_yaml("instructions/manifest.yml")
    phases = {
        phase.get("id"): phase
        for phase in manifest.get("phases", [])
        if isinstance(phase, dict) and phase.get("id")
    }
    if "review_curriculum" in phases or "materialize_content" in phases:
        fail("review and materialization must remain internal")
    if phases.get("generate", {}).get("next_phase") != "publish":
        fail("generate must route to publish")
    if phases.get("publish", {}).get("next_phase") != "evaluate":
        fail("publish must route to evaluate")
    if phases.get("evaluate", {}).get("internal_materialization") != "instructions/57-materialize-next-content.md":
        fail("evaluation must retain automatic materialization")


def validate_instance_config() -> dict[str, Any]:
    config_path = ".open-study-path/instance.yml" if INSTANCE.is_file() else "templates/instance.yml"
    document = load_yaml(config_path)
    workflow = document.get("workflow", {})
    if workflow.get("curriculum_merge_policy") not in {"manual", "agent_review_then_merge"}:
        fail(f"invalid curriculum merge policy in {config_path}")
    generation = document.get("content_generation", {})
    if generation.get("strategy") not in {"adaptive_rolling_window", "full_upfront"}:
        fail(f"invalid content generation strategy in {config_path}")
    visual = generation.get("visual_learning", {})
    if visual.get("mermaid_enabled") is not True:
        fail(f"{config_path} must enable Mermaid")
    if not isinstance(visual.get("minimum_diagrams_per_materialized_module"), int):
        fail(f"{config_path} must define a diagram minimum")
    return document


def validate_contract_terms() -> None:
    require("docs/learner-facing-language.md", [
        "Quatro perguntas da resposta principal",
        "O próximo passo vem do estado",
        "Responsabilidade por adiamentos sugeridos",
        "Organize minha trilha nas ferramentas que escolhemos.",
        "Não acrescente um comando de avaliação nesse estado.",
    ])
    require("docs/content-quality-and-sources.md", [
        "Como este conteúdo foi construído",
        "Fontes e caminhos para aprofundar",
        "no mínimo três fontes",
        "timestamp",
    ])
    require("instructions/phase-completion.md", [
        "Do not foreground PR numbers",
        "scripts/lifecycle_next_action.py",
        "The agent owns that deferral",
        "single copyable continuation",
        "Do not include `Terminei <título da aula>. Avalie minhas respostas.`",
    ])
    require("instructions/30-generate-path.md", [
        "Source and provenance contract",
        "Other ways to learn",
        "three to seven curated sources",
        "scripts/lifecycle_next_action.py",
        "Do not present `Terminei <título da aula>. Avalie minhas respostas.` as the next command before publication succeeds.",
    ])
    require("instructions/35-review-curriculum.md", [
        "Source and content review",
        "learner-facing prose",
        "Trello card text uses human titles",
    ])
    require("instructions/40-publish-tasks.md", [
        "Human card titles",
        "Sua sessão de estudo",
        "A aula completa será preparada automaticamente",
        "Persist publication completion",
        "sync.status",
        "sync.last_success_at",
        "scripts/lifecycle_next_action.py",
        "Do not report an inventory of inactive integrations",
    ])
    require("templates/module.md", [
        "## Como este conteúdo foi construído",
        "## Fontes e caminhos para aprofundar",
        "## Outras formas de aprender",
        "## Confira sem consultar",
        "Não gere flashcards, decks Markdown, arquivos TSV ou conjuntos em serviços externos.",
    ])
    require("templates/topic.md", [
        "## O que você vai aprender",
        "## Por que isso importa para você",
        "## Para concluir esta etapa",
        "não crie decks, arquivos de importação",
    ])
    require("templates/integrations-plan.md", [
        "# Ferramentas que podem ajudar nesta trilha",
        "<details>",
    ])
    require("README.md", [
        "Agent pilot",
        "ANTHROPIC_API_KEY",
        "Conteúdo com fontes",
        "Linguagem voltada para quem estuda",
    ])
    require("AGENTS.md", [
        "Do not lead with PR, CI",
        "scripts/lifecycle_next_action.py",
        "The agent must restore publication",
        "Human task titles",
    ])

    for path in [
        "scripts/lifecycle_next_action.py",
        "scripts/test_lifecycle_next_action.py",
    ]:
        if not (ROOT / path).is_file():
            fail(f"missing lifecycle routing regression asset: {path}")

    workflow = read(".github/workflows/validate-template.yml")
    if "python scripts/test_lifecycle_next_action.py" not in workflow:
        fail("validation workflow must run lifecycle next-action regressions")


def validate_next_action_regression() -> None:
    generated = {"status": {"curriculum_generated": True}}

    for integration_state in [
        None,
        {"sync": {"status": "not_started", "last_success_at": None}},
        {"sync": {"status": "partial", "last_success_at": None}},
        {"sync": {"status": "failed", "last_success_at": None}},
    ]:
        action = resolve_next_action(generated, integration_state)
        if action.phase != "publish" or action.command != PUBLISH_COMMAND:
            fail("generated curriculum without completed publication must route to publish")
        if "Avalie minhas respostas" in action.command:
            fail("evaluation command leaked before publication completion")

    completed = {
        "sync": {
            "status": "success",
            "last_success_at": "2026-07-28T22:00:00Z",
        }
    }
    action = resolve_next_action(generated, completed, lesson_title="Aula inicial")
    if action.phase != "evaluate" or action.command != "Terminei Aula inicial. Avalie minhas respostas.":
        fail("completed publication must enable the evaluation continuation")


def validate_generated(document: dict[str, Any]) -> None:
    topics_dir = ROOT / "study/topics"
    if not topics_dir.is_dir():
        return

    topics = sorted(topics_dir.glob("TOPIC-*.md"))
    if not topics:
        return

    roadmap = ROOT / "study/roadmap.md"
    if not roadmap.is_file() or not MERMAID.findall(read(roadmap)):
        fail("generated roadmap must contain a Mermaid dependency diagram")

    minimum = document["content_generation"]["visual_learning"]["minimum_diagrams_per_materialized_module"]
    for topic_path in topics:
        metadata, _ = parse_frontmatter(topic_path)
        if metadata.get("content_status") != "materialized":
            continue
        topic_id = metadata.get("id")
        module_value = metadata.get("module")
        if not isinstance(module_value, str):
            fail(f"materialized topic {topic_id} must define a module")
        module_path = ROOT / module_value
        # Modules deliberately have no YAML frontmatter -- published lesson
        # Markdown begins directly with its title and learning content, per
        # the same convention validate_learning_experience.py's
        # validate_generated_modules() enforces (it fails a module that
        # *does* expose frontmatter). This function used to call
        # parse_frontmatter(module_path) here, which unconditionally failed
        # every real materialized module with "missing frontmatter" --
        # never caught because this check sat behind an unapproved
        # action_required CI run until a real Etapa 6c evaluate dispatch
        # surfaced it.
        body = read(module_path)
        diagrams = MERMAID.findall(body)
        if len(diagrams) < minimum:
            fail(f"module {topic_id} has fewer Mermaid diagrams than configured")
        for section in [
            "## Mapa visual",
            "## Outras formas de aprender",
            "## Como este conteúdo foi construído",
            "## Fontes e caminhos para aprofundar",
        ]:
            if section not in body:
                fail(f"module {topic_id} is missing section: {section}")
        source_section = body.split("## Fontes e caminhos para aprofundar", 1)[1]
        links = LINK.findall(source_section)
        if len(set(links)) < 3:
            fail(f"module {topic_id} needs at least three verified source links")
        if "Como foi usada" not in source_section and "Como foi usado" not in source_section:
            fail(f"module {topic_id} must explain how sources were used")
        # visual_diagrams was previously read from the module's own (now
        # nonexistent) frontmatter as a second, declared-vs-actual check.
        # The len(diagrams) < minimum check above already verifies the real
        # diagram count directly from content -- a frontmatter-declared
        # count would only ever be a duplicate, weaker signal (the model
        # could declare a number without it matching reality), not
        # additional guarantee, so it is not reimplemented against a field
        # that no longer exists rather than invented as a new requirement.


def main() -> None:
    validate_manifest()
    document = validate_instance_config()
    validate_contract_terms()
    validate_next_action_regression()
    validate_generated(document)
    print("Guided lifecycle, state-derived continuation and source-rich lessons passed.")


if __name__ == "__main__":
    main()
