#!/usr/bin/env python3
"""Validate curriculum lifecycle, rolling materialization and assessments."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
INSTANCE_MARKER = ROOT / ".open-study-path/instance.yml"
TOPICS_DIR = ROOT / "study/topics"
MODULES_DIR = ROOT / "study/modules"
ASSESSMENTS_DIR = ROOT / "study/assessments"
ISSUE_FORMS_DIR = ROOT / ".github/ISSUE_TEMPLATE"
ROADMAP = ROOT / "study/roadmap.md"
ASSESSMENT_STATE = ROOT / "state/assessments"
ALLOWED_CURRICULUM_POLICIES = {"manual", "agent_review_then_merge"}
ALLOWED_CONTENT_STRATEGIES = {"adaptive_rolling_window", "full_upfront"}
ALLOWED_CONTENT_STATUS = {"planned", "materialized"}
TOPIC_HEADINGS = [
    "## Objective",
    "## Why this matters",
    "## Prerequisites",
    "## Learning activities",
    "## Complete module",
    "## Assessment",
    "## Deliverable",
    "## Evidence",
    "## Mastery criteria",
    "## Resources",
]
MODULE_HEADINGS = [
    "## Como usar este módulo",
    "## Plano de execução",
    "## Objetivos de aprendizagem",
    "## Verificação de pré-requisitos",
    "## Conteúdo essencial",
    "## Exemplos trabalhados",
    "## Erros comuns e como corrigi-los",
    "## Prática guiada",
    "## Prática independente",
    "## Síntese por recuperação ativa",
    "## Entregável e evidência",
    "## Avaliação do tópico",
    "## Referências",
]
VAGUE_REQUIRED_RESOURCE = re.compile(
    r"(?:a selecionar|passagem curta|uma introdução|trecho e tradução a revisar|"
    r"edição ou tradução a revisar|com edição a revisar)",
    re.IGNORECASE,
)
CANONICAL_LOCATOR = re.compile(r"(?:§|\b\d+\b|\b[IVXLCDM]+\.)")
PLACEHOLDER_CONTENT = re.compile(
    r"(?:replace me|substitua por|estude o conceito|study the core concept|"
    r"descreva o|inclua exercícios|apresente ao menos)",
    re.IGNORECASE,
)
DURATION = re.compile(r"\((\d+)\s*min\)", re.IGNORECASE)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"missing YAML frontmatter: {path.relative_to(ROOT)}")
    try:
        _, frontmatter, body = text.split("---", 2)
    except ValueError:
        fail(f"malformed frontmatter: {path.relative_to(ROOT)}")
    document = yaml.safe_load(frontmatter)
    if not isinstance(document, dict):
        fail(f"frontmatter must be an object: {path.relative_to(ROOT)}")
    return document, body


def section(body: str, heading: str) -> str:
    match = re.search(
        rf"^{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def checkbox_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if re.match(r"^- \[[ xX]\] ", line.strip())]


def required_resource_lines(body: str, path: Path) -> list[str]:
    match = re.search(
        r"### Required\s*(.*?)(?:\n### Optional|\n## Prompt to start a study chat|\Z)",
        body,
        re.DOTALL,
    )
    if not match:
        fail(f"missing Required resources subsection: {path.relative_to(ROOT)}")
    lines = [line.strip()[2:].strip() for line in match.group(1).splitlines() if line.strip().startswith("- ")]
    if not lines:
        fail(f"must contain at least one required resource: {path.relative_to(ROOT)}")
    return lines


def content_config(document: dict[str, Any], path: str) -> dict[str, Any]:
    config = document.get("content_generation")
    if not isinstance(config, dict):
        fail(f"{path} must define content_generation")
    strategy = config.get("strategy")
    if strategy not in ALLOWED_CONTENT_STRATEGIES:
        fail(f"invalid content_generation.strategy in {path}: {strategy}")
    for key in ["lookahead_topics", "full_upfront_max_topics"]:
        if not isinstance(config.get(key), int) or config[key] < 1:
            fail(f"{path} must define positive integer {key}")
    hours = config.get("full_upfront_max_hours")
    if not isinstance(hours, (int, float)) or hours <= 0:
        fail(f"{path} must define positive full_upfront_max_hours")
    if config.get("adapt_future_modules_from_assessments") is not True:
        fail(f"{path} must enable assessment-informed future modules")
    granularity = config.get("granularity")
    if not isinstance(granularity, dict):
        fail(f"{path} must define content_generation.granularity")
    required = [
        "activity_minutes_min", "activity_minutes_max",
        "activities_per_topic_min", "activities_per_topic_max",
        "topic_minutes_target_min", "topic_minutes_target_max",
        "split_topic_above_minutes",
    ]
    if not all(isinstance(granularity.get(key), int) for key in required):
        fail(f"{path} granularity values must be integers")
    if not 1 <= granularity["activity_minutes_min"] <= granularity["activity_minutes_max"]:
        fail(f"invalid activity-minute range in {path}")
    if not 1 <= granularity["activities_per_topic_min"] <= granularity["activities_per_topic_max"]:
        fail(f"invalid activities-per-topic range in {path}")
    if not 1 <= granularity["topic_minutes_target_min"] <= granularity["topic_minutes_target_max"]:
        fail(f"invalid topic-minute target range in {path}")
    if granularity["split_topic_above_minutes"] < granularity["topic_minutes_target_max"]:
        fail(f"split threshold must not be below target maximum in {path}")
    return config


def check_lifecycle_contract() -> dict[str, Any]:
    manifest = load_yaml(ROOT / "instructions/manifest.yml")
    phases = {phase.get("id"): phase for phase in manifest.get("phases", []) if isinstance(phase, dict)}
    if "review_curriculum" in phases or "materialize_content" in phases:
        fail("review and materialization must remain internal operations")

    generate = phases.get("generate", {})
    if generate.get("next_phase") != "publish":
        fail("generation must route to publish")
    if generate.get("internal_review") != "instructions/35-review-curriculum.md":
        fail("generation must reference internal review")
    if generate.get("merge_policy_path") != "workflow.curriculum_merge_policy":
        fail("generation must reference workflow.curriculum_merge_policy")

    publish = phases.get("publish", {})
    if publish.get("depends_on") != ["generate"] or publish.get("next_phase") != "evaluate":
        fail("publish must depend on generation and route to evaluate")

    evaluate = phases.get("evaluate", {})
    if evaluate.get("instruction") != "instructions/55-evaluate-topic.md":
        fail("evaluate phase must reference topic evaluation")
    if evaluate.get("internal_materialization") != "instructions/57-materialize-next-content.md":
        fail("evaluate must reference internal rolling materialization")

    required_files = [
        "instructions/30-generate-path.md",
        "instructions/35-review-curriculum.md",
        "instructions/55-evaluate-topic.md",
        "instructions/57-materialize-next-content.md",
        "templates/module.md",
        "templates/assessment-rubric.yml",
        "templates/topic-assessment-issue-form.yml",
    ]
    for required in required_files:
        if not (ROOT / required).is_file():
            fail(f"missing curriculum file: {required}")

    template = load_yaml(ROOT / "templates/instance.yml")
    if template.get("workflow", {}).get("curriculum_merge_policy") != "agent_review_then_merge":
        fail("new instances must default curriculum merge to agent_review_then_merge")
    config = content_config(template, "templates/instance.yml")

    if INSTANCE_MARKER.is_file():
        marker = load_yaml(INSTANCE_MARKER)
        policy = marker.get("workflow", {}).get("curriculum_merge_policy")
        if policy not in ALLOWED_CURRICULUM_POLICIES:
            fail(f"invalid curriculum_merge_policy: {policy}")
        config = content_config(marker, ".open-study-path/instance.yml")
    return config


def detect_cycle(prerequisites: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(topic_id: str) -> None:
        if topic_id in visited:
            return
        if topic_id in visiting:
            fail(f"curriculum dependency cycle detected at {topic_id}")
        visiting.add(topic_id)
        for prerequisite in prerequisites[topic_id]:
            visit(prerequisite)
        visiting.remove(topic_id)
        visited.add(topic_id)

    for topic_id in prerequisites:
        visit(topic_id)


def topological_order(prerequisites: dict[str, list[str]]) -> list[str]:
    remaining = {topic: set(required) for topic, required in prerequisites.items()}
    order: list[str] = []
    while remaining:
        ready = sorted(topic for topic, required in remaining.items() if not required)
        if not ready:
            fail("cannot derive deterministic topological order")
        for topic in ready:
            order.append(topic)
            remaining.pop(topic)
        for required in remaining.values():
            required.difference_update(ready)
    return order


def check_duration_items(topic_id: str, items: list[str], config: dict[str, Any], where: str) -> None:
    granularity = config["granularity"]
    minimum = granularity["activities_per_topic_min"]
    maximum = granularity["activities_per_topic_max"]
    if not minimum <= len(items) <= maximum:
        fail(f"{where} for {topic_id} must contain {minimum}..{maximum} checkbox actions")
    for item in items:
        match = DURATION.search(item)
        if not match:
            fail(f"{where} action for {topic_id} is missing a numeric minute estimate: {item}")
        minutes = int(match.group(1))
        if not granularity["activity_minutes_min"] <= minutes <= granularity["activity_minutes_max"]:
            fail(f"{where} action for {topic_id} has invalid duration: {minutes} min")


def check_module(topic_id: str, path: Path, config: dict[str, Any]) -> None:
    metadata, body = parse_frontmatter(path)
    if metadata.get("topic_id") != topic_id:
        fail(f"module topic_id mismatch for {topic_id}")
    minutes = metadata.get("estimated_minutes")
    if not isinstance(minutes, int) or minutes <= 0:
        fail(f"module {topic_id} must define positive estimated_minutes")
    if minutes > config["granularity"]["split_topic_above_minutes"]:
        fail(f"module {topic_id} exceeds split threshold: {minutes} minutes")
    for heading in MODULE_HEADINGS:
        if heading not in body:
            fail(f"module {topic_id} is missing heading: {heading}")
    words = re.findall(r"\b\w+\b", body, flags=re.UNICODE)
    if len(words) < 500:
        fail(f"module {topic_id} is too short to be complete: {len(words)} words")
    if PLACEHOLDER_CONTENT.search(body):
        fail(f"module {topic_id} contains template placeholder content")
    if body.count("### Exemplo") + body.count("**Exemplo") < 2:
        fail(f"module {topic_id} must contain at least two worked examples")
    check_duration_items(topic_id, checkbox_lines(section(body, "## Plano de execução")), config, "module plan")
    if f"Finalizei o {topic_id}. Avalie minhas respostas." not in body:
        fail(f"module {topic_id} is missing the standard assessment command")


def check_rubric(topic_id: str, path: Path) -> None:
    rubric = load_yaml(path)
    if not isinstance(rubric, dict) or rubric.get("topic_id") != topic_id:
        fail(f"invalid rubric topic_id for {topic_id}")
    passing = rubric.get("passing_score")
    if not isinstance(passing, int) or not 1 <= passing <= 100:
        fail(f"invalid passing_score for {topic_id}")
    questions = rubric.get("questions")
    if not isinstance(questions, list) or len(questions) != 5:
        fail(f"rubric {topic_id} must define exactly five questions")
    if [item.get("id") for item in questions if isinstance(item, dict)] != ["q1", "q2", "q3", "q4", "q5"]:
        fail(f"rubric {topic_id} question ids must be q1..q5")
    points = [item.get("max_points") for item in questions]
    if not all(isinstance(point, int) and point > 0 for point in points) or sum(points) != 100:
        fail(f"rubric {topic_id} must total 100 points")
    for item in questions:
        for key in ["evaluates", "full_credit", "partial_credit", "no_credit"]:
            if not isinstance(item.get(key), str) or not item[key].strip():
                fail(f"rubric {topic_id} question {item.get('id')} is missing {key}")


def check_issue_form(topic_id: str, path: Path) -> None:
    form = load_yaml(path)
    if not isinstance(form, dict):
        fail(f"invalid assessment Issue Form for {topic_id}")
    if topic_id not in str(form.get("name", "")) or topic_id not in str(form.get("title", "")):
        fail(f"assessment Issue Form does not identify {topic_id}")
    labels = form.get("labels")
    if not isinstance(labels, list) or not {"assessment", "assessment:submitted"}.issubset(set(labels)):
        fail(f"assessment Issue Form {topic_id} is missing standard labels")
    body = form.get("body")
    if not isinstance(body, list):
        fail(f"assessment Issue Form body must be a list for {topic_id}")
    ids = [entry.get("id") for entry in body if isinstance(entry, dict)]
    for question_id in ["q1", "q2", "q3", "q4", "q5", "confirmation"]:
        if question_id not in ids:
            fail(f"assessment Issue Form {topic_id} is missing {question_id}")
    serialized = path.read_text(encoding="utf-8")
    if f"open-study-path:assessment topic_id={topic_id}" not in serialized:
        fail(f"assessment Issue Form {topic_id} is missing deterministic topic marker")
    if f"Finalizei o {topic_id}. Avalie minhas respostas." not in serialized:
        fail(f"assessment Issue Form {topic_id} is missing standard return command")


def check_initial_window(
    topics: dict[str, dict[str, Any]],
    prerequisites: dict[str, list[str]],
    config: dict[str, Any],
) -> None:
    if ASSESSMENT_STATE.is_dir() and any(ASSESSMENT_STATE.rglob("attempt-*.json")):
        return
    materialized = {topic for topic, metadata in topics.items() if metadata["content_status"] == "materialized"}
    strategy = config["strategy"]
    total_hours = sum(float(metadata["estimated_hours"]) for metadata in topics.values())
    small = len(topics) <= config["full_upfront_max_topics"] and total_hours <= config["full_upfront_max_hours"]
    if strategy == "full_upfront" or small:
        if materialized != set(topics):
            fail("small or full-upfront curriculum must materialize every topic")
        return
    order = topological_order(prerequisites)
    expected = set(order[: min(config["lookahead_topics"], len(order))])
    if materialized != expected:
        fail(f"initial rolling window must materialize deterministic prefix {sorted(expected)}")


def check_topics(config: dict[str, Any]) -> None:
    topic_paths = sorted(TOPICS_DIR.glob("*.md")) if TOPICS_DIR.is_dir() else []
    if not topic_paths:
        print("No generated curriculum topics to validate.")
        return
    if not ROADMAP.is_file():
        fail("generated topics require study/roadmap.md")

    topics: dict[str, dict[str, Any]] = {}
    prerequisites: dict[str, list[str]] = {}
    roadmap = ROADMAP.read_text(encoding="utf-8")

    for path in topic_paths:
        metadata, body = parse_frontmatter(path)
        required_keys = [
            "id", "title", "status", "content_status", "content_version", "materialized_at",
            "difficulty", "estimated_hours", "prerequisites", "module", "assessment", "assessment_form",
        ]
        for key in required_keys:
            if key not in metadata:
                fail(f"topic is missing frontmatter key {key}: {path.relative_to(ROOT)}")
        topic_id = metadata["id"]
        if not isinstance(topic_id, str) or not topic_id:
            fail(f"topic id must be non-empty: {path.relative_to(ROOT)}")
        if topic_id in topics:
            fail(f"duplicate topic id: {topic_id}")
        if metadata["content_status"] not in ALLOWED_CONTENT_STATUS:
            fail(f"invalid content_status for {topic_id}: {metadata['content_status']}")
        hours = metadata["estimated_hours"]
        if not isinstance(hours, (int, float)) or hours <= 0:
            fail(f"estimated_hours must be positive for {topic_id}")
        topic_prerequisites = metadata["prerequisites"]
        if not isinstance(topic_prerequisites, list) or not all(isinstance(item, str) for item in topic_prerequisites):
            fail(f"prerequisites must be a string array for {topic_id}")
        for heading in TOPIC_HEADINGS:
            if heading not in body:
                fail(f"topic {topic_id} is missing heading: {heading}")
        check_duration_items(topic_id, checkbox_lines(section(body, "## Learning activities")), config, "topic activities")
        for resource in required_resource_lines(body, path):
            if VAGUE_REQUIRED_RESOURCE.search(resource) and not CANONICAL_LOCATOR.search(resource):
                fail(f"required resource is vague in {topic_id}: {resource}")
            if not CANONICAL_LOCATOR.search(resource):
                fail(f"required resource needs a canonical locator in {topic_id}: {resource}")
        if topic_id not in roadmap:
            fail(f"roadmap does not reference topic {topic_id}")

        expected_module = f"study/modules/{topic_id}.md"
        expected_rubric = f"study/assessments/{topic_id}.yml"
        suffix = topic_id.split("-")[-1].lower()
        expected_form = f".github/ISSUE_TEMPLATE/assessment-topic-{suffix}.yml"
        declared_module = metadata["module"]
        # Etapa 6d follow-up: a real dispatch's own read-back validation
        # requires the materialized module's own file path to avoid
        # containing its topic_id (a metadata-leak the learner-facing
        # resource URL must never expose -- see AUTHOR_DETAILED_NOTE/
        # AUTHOR_EVALUATE_NOTE in scripts/build_agent_prompt.py), so content
        # materialized after that fix uses a slug filename derived from the
        # topic's title (e.g. study/modules/a-dicotomia-do-controle.md)
        # instead of study/modules/{topic_id}.md. Content materialized
        # before that fix (e.g. TOPIC-001) still legitimately uses the
        # {topic_id}.md convention. Accept either: what matters is that the
        # frontmatter's declared module path is a real .md file directly
        # under study/modules/, not that it follows one specific naming
        # scheme -- a real evaluate dispatch materializing TOPIC-003 with a
        # correct slug filename still failed this check outright when it
        # only accepted the older convention.
        module_is_consistent = (
            declared_module == expected_module
            or (
                isinstance(declared_module, str)
                and declared_module.startswith("study/modules/")
                and declared_module.endswith(".md")
                and "/" not in declared_module.removeprefix("study/modules/")
            )
        )
        if not module_is_consistent or metadata["assessment"] != expected_rubric or metadata["assessment_form"] != expected_form:
            fail(f"topic {topic_id} artifact paths are inconsistent")
        artifacts = [ROOT / declared_module, ROOT / expected_rubric, ROOT / expected_form]

        if metadata["content_status"] == "materialized":
            if not isinstance(metadata["content_version"], int) or metadata["content_version"] < 1:
                fail(f"materialized topic {topic_id} needs positive content_version")
            if not isinstance(metadata["materialized_at"], str) or not metadata["materialized_at"].strip():
                fail(f"materialized topic {topic_id} needs materialized_at")
            for artifact in artifacts:
                if not artifact.is_file():
                    fail(f"missing materialized artifact for {topic_id}: {artifact.relative_to(ROOT)}")
            check_module(topic_id, artifacts[0], config)
            check_rubric(topic_id, artifacts[1])
            check_issue_form(topic_id, artifacts[2])
        else:
            if metadata["content_version"] != 0 or metadata["materialized_at"] is not None:
                fail(f"planned topic {topic_id} must use version 0 and null materialized_at")
            for artifact in artifacts:
                if artifact.exists():
                    fail(f"planned topic {topic_id} must not have materialized artifact: {artifact.relative_to(ROOT)}")

        topics[topic_id] = metadata
        prerequisites[topic_id] = topic_prerequisites

    for topic_id, required_ids in prerequisites.items():
        for required_id in required_ids:
            if required_id not in topics:
                fail(f"topic {topic_id} references missing prerequisite {required_id}")
            if required_id == topic_id:
                fail(f"topic {topic_id} cannot depend on itself")

    detect_cycle(prerequisites)
    check_initial_window(topics, prerequisites, config)
    materialized_count = sum(metadata["content_status"] == "materialized" for metadata in topics.values())
    print(f"Rolling curriculum contract passed for {len(topics)} topics ({materialized_count} materialized).")


def main() -> None:
    config = check_lifecycle_contract()
    check_topics(config)
    print("Curriculum validation passed.")


if __name__ == "__main__":
    main()
