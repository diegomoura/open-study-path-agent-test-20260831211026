#!/usr/bin/env python3
"""Validate learner-facing language, progressive lessons and sources."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

from beginner_pedagogy import validate_module_pedagogy

ROOT = Path(__file__).resolve().parents[1]
INSTANCE = ROOT / ".open-study-path/instance.yml"
TOPICS = ROOT / "study/topics"
MODULES = ROOT / "study/modules"
ISSUE_FORMS = ROOT / ".github/ISSUE_TEMPLATE"
LINK = re.compile(r"https?://[^\s)>]+")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def text(path: str | Path) -> str:
    target = ROOT / path if isinstance(path, str) else path
    if not target.is_file():
        fail(f"missing learner-experience file: {target.relative_to(ROOT)}")
    return target.read_text(encoding="utf-8")


def load_yaml(path: str | Path) -> Any:
    return yaml.safe_load(text(path))


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    content = text(path)
    if not content.startswith("---\n"):
        fail(f"missing frontmatter: {path.relative_to(ROOT)}")
    try:
        _, raw, body = content.split("---", 2)
    except ValueError:
        fail(f"malformed frontmatter: {path.relative_to(ROOT)}")
    metadata = yaml.safe_load(raw)
    if not isinstance(metadata, dict):
        fail(f"frontmatter must be an object: {path.relative_to(ROOT)}")
    return metadata, body


def require_terms(path: str, terms: list[str]) -> None:
    content = text(path)
    for term in terms:
        if term not in content:
            fail(f"{path} is missing learner-experience term: {term}")


def forbid_terms(path: str, terms: list[str]) -> None:
    content = text(path).lower()
    for term in terms:
        if term.lower() in content:
            fail(f"{path} retains removed learner-experience term: {term}")


def validate_contracts() -> None:
    module_template = text("templates/module.md")
    if module_template.startswith("---\n"):
        fail("lesson template must not expose YAML frontmatter")
    require_terms("templates/module.md", [
        "Não adicione frontmatter YAML a este arquivo",
        "## Começando do zero",
        "### Vocabulário desta aula",
        "## Intuição antes dos detalhes",
        "**Analogia:**",
        "**Onde a analogia deixa de funcionar:**",
        "## Prática guiada",
        "## Prática independente",
        "## Confira sem consultar",
        "Não gere flashcards, decks Markdown, arquivos TSV ou conjuntos em serviços externos.",
        "issues/new?template=assessment-topic-000.yml",
        "## Como este conteúdo foi construído",
        "## Fontes e caminhos para aprofundar",
        "Terminei <título da aula>. Avalie minhas respostas.",
    ])
    require_terms("templates/topic.md", [
        "## O que você vai aprender",
        "## Por que isso importa para você",
        "não é uma página de navegação principal",
        "aula publicada não recebe frontmatter YAML",
        "Não apresente a rubrica YAML como link normal",
        "Esta aula será preparada automaticamente",
        "não crie decks, arquivos de importação",
    ])
    forbid_terms("templates/topic.md", ["flashcards:", "flashcards_study:"])
    require_terms("instructions/phase-completion.md", [
        "Do not foreground PR numbers",
        "Preenchi o formulário. Pode continuar.",
        "Organize minha trilha nas ferramentas que escolhemos.",
        "Do not append a provider inventory",
    ])
    require_terms("instructions/30-generate-path.md", [
        "docs/beginner-first-pedagogy.md",
        "Do not create flashcards, Markdown decks, TSV exports or Quizlet sets.",
        "active recall inside the lesson",
    ])
    require_terms("instructions/40-publish-tasks.md", [
        "One primary resource per capability",
        "Never create flashcard Markdown, TSV exports or Quizlet sets.",
        "Do not report an inventory of inactive integrations",
        "The future card must stand on its own",
        "Sua sessão de estudo",
    ])
    require_terms("docs/learner-facing-language.md", [
        "Uma interface não é um inventário",
        "contratos internos em `study/topics/`",
        "Terminei <título da aula>. Avalie minhas respostas.",
    ])
    require_terms("AGENTS.md", [
        "A task backend is not a repository inventory",
        "Do not generate flashcards, Markdown decks, TSV exports or Quizlet sets.",
        "Read `docs/beginner-first-pedagogy.md`",
    ])
    require_terms("docs/content-quality-and-sources.md", [
        "no mínimo três fontes",
        "Antes de citar",
        "Vídeos",
        "Cursos e plataformas",
        "Analogia não é evidência",
        "cenário realista",
    ])

    issue = load_yaml("templates/topic-assessment-issue-form.yml")
    if issue.get("title") != "[Avaliação] TOPIC-000 — Replace me":
        fail("assessment form must prefill the complete title")

    intake = load_yaml(".github/ISSUE_TEMPLATE/create-study-path.yml")
    if intake.get("name") != "Criar meu curso":
        fail("intake form must use learner-facing course language")
    if intake.get("title") not in (None, ""):
        fail("intake issue title must be entered by the learner as the course name")


def validate_generated_modules() -> None:
    if not INSTANCE.is_file() or not MODULES.is_dir():
        return

    instance = load_yaml(INSTANCE)
    repository = instance.get("repository") if isinstance(instance, dict) else None
    if not isinstance(repository, str) or "/" not in repository:
        fail("instance repository identity is required")

    for module_path in sorted(MODULES.glob("TOPIC-*.md")):
        body = text(module_path)
        if body.startswith("---\n"):
            fail(f"module exposes operational YAML frontmatter: {module_path.relative_to(ROOT)}")

        topic_id = module_path.stem
        topic_path = TOPICS / f"{topic_id}.md"
        metadata, _ = parse_frontmatter(topic_path)
        title = metadata.get("title")
        if metadata.get("id") != topic_id or not isinstance(title, str):
            fail(f"topic contract identity is incomplete for {topic_id}")
        if not re.search(rf"^#\s+(?:\d+\.\s+|{re.escape(topic_id)}\s+[—-]\s+)?{re.escape(title)}\s*$", body, re.MULTILINE):
            fail(f"module {topic_id} must begin with its learner-facing title")

        for error in validate_module_pedagogy(title, body, str(metadata.get("difficulty", ""))):
            fail(f"module {topic_id} {error}")

        suffix = topic_id.split("-")[-1].lower()
        form_name = f"assessment-topic-{suffix}.yml"
        direct_url = f"https://github.com/{repository}/issues/new?template={form_name}"
        if direct_url not in body:
            fail(f"module {topic_id} must contain its direct assessment URL")

        form = load_yaml(ISSUE_FORMS / form_name)
        if form.get("title") != f"[Avaliação] {topic_id} — {title}":
            fail(f"assessment form {topic_id} must prefill the complete title")

        for section in [
            "## Prática guiada",
            "## Prática independente",
            "## Confira sem consultar",
            "## Outras formas de aprender",
            "## Como este conteúdo foi construído",
            "## Fontes e caminhos para aprofundar",
        ]:
            if section not in body:
                fail(f"module {topic_id} is missing: {section}")

        source_section = body.split("## Fontes e caminhos para aprofundar", 1)[1]
        if len(set(LINK.findall(source_section))) < 3:
            fail(f"module {topic_id} needs at least three source links")
        if "Como foi usada" not in source_section and "Como foi usado" not in source_section:
            fail(f"module {topic_id} must explain source use")

        for removed in ["flashcards_study", "study/flashcards/", "Praticar no Quizlet", "Baixar ou importar o TSV"]:
            if removed in body or removed in metadata:
                fail(f"module {topic_id} retains removed flashcard artifact: {removed}")


def main() -> None:
    validate_contracts()
    validate_generated_modules()
    print("Progressive learner language, metadata-free lessons, sources and assessments passed.")


if __name__ == "__main__":
    main()
