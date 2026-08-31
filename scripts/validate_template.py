#!/usr/bin/env python3
"""Validate an Open Study Path repository in template or instance mode."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
INSTANCE_MARKER = ".open-study-path/instance.yml"
TEMPLATE_MARKER = ".open-study-path/template.yml"
COMPLETION_CONTRACT = "instructions/phase-completion.md"
DIAGNOSTIC_TEMPLATE = "templates/state/diagnostic-summary.json"
DIAGNOSTIC_SCHEMA = "schemas/diagnostic-summary.schema.json"
DIAGNOSTIC_STATE = "state/diagnostic-summary.json"
CURRENT_INTAKE_MARKER = "<!-- open-study-path:intake form_id=create-study-path version=4 -->"
MERGE_POLICIES = {"manual", "auto_after_ci", "auto_when_unambiguous"}
DIAGNOSTIC_EXCEPTIONS = {None, "owner_requested_comprehensive", "legacy_before_policy"}

REUSABLE_YAML_FILES = [
    TEMPLATE_MARKER,
    ".github/ISSUE_TEMPLATE/create-study-path.yml",
    "instructions/manifest.yml",
    "intake/jotform-form-spec.yml",
    "intake/field-mapping.yml",
    "study.config.example.yml",
    "templates/instance.yml",
]

REQUIRED_REUSABLE_FILES = [
    "README.md",
    "AGENTS.md",
    "docs/claude-agent-setup.md",
    "docs/integration-capabilities.md",
    "templates/integrations-plan.md",
    "templates/integrations-state.json",
    "instructions/00-bootstrap.md",
    "instructions/05-configure-intake.md",
    "instructions/10-intake.md",
    "instructions/20-diagnostic.md",
    COMPLETION_CONTRACT,
    DIAGNOSTIC_TEMPLATE,
    DIAGNOSTIC_SCHEMA,
]

INSTANCE_ARTIFACTS = [
    INSTANCE_MARKER,
    "study.config.yml",
    "state/intake-summary.json",
    "state/progress.json",
    "study/roadmap.md",
]

REQUIRED_INTAKE_KEYS = {
    "subject",
    "objective",
    "current_level",
    "preferred_language",
    "integration_experience",
    "already_uses",
    "willing_to_connect",
    "task_manager",
    "study_routine_mode",
    "study_routine_details",
    "consent",
}

REMOVED_INTAKE_KEYS = {
    "weekly_hours",
    "deadline",
    "preferred_days",
    "preferred_periods",
    "free_tier_only",
    "account_connections",
    "scheduling_provider",
    "integration_notes",
    "todoist_reminders",
    "email_summaries",
}


def load_yaml(path: str) -> Any:
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: str) -> Any:
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def is_instance() -> bool:
    return (ROOT / INSTANCE_MARKER).is_file()


def check_yaml() -> None:
    paths = list(REUSABLE_YAML_FILES)
    if is_instance():
        paths.extend([INSTANCE_MARKER, "study.config.yml"])
    for path in paths:
        if not (ROOT / path).is_file():
            fail(f"missing required YAML file: {path}")
        load_yaml(path)
    print("YAML parsing passed.")


def validate_workflow_policy(document: dict[str, Any], *, required: bool) -> None:
    workflow = document.get("workflow")
    if workflow is None:
        if required:
            fail("instance marker template must define workflow defaults")
        return
    if not isinstance(workflow, dict):
        fail("instance marker workflow must be an object")
    if workflow.get("guided") is not True:
        fail("instance workflow must set guided: true")
    for key in ["intake_merge_policy", "diagnostic_merge_policy"]:
        if workflow.get(key) not in MERGE_POLICIES:
            fail(f"invalid {key}: {workflow.get(key)}")


def validate_diagnostic_budget(document: dict[str, Any], path: str) -> None:
    budget = document.get("question_budget", {})
    values = [budget.get("target_min"), budget.get("target_max"), budget.get("hard_max"), document.get("question_count")]
    if not all(isinstance(value, int) for value in values):
        fail(f"diagnostic budget values must be integers in {path}")
    target_min, target_max, hard_max, count = values
    if not (1 <= target_min <= target_max <= hard_max <= 10):
        fail(f"invalid diagnostic question budget in {path}")
    exception = budget.get("exception")
    if exception not in DIAGNOSTIC_EXCEPTIONS:
        fail(f"invalid diagnostic budget exception in {path}: {exception}")
    if count > hard_max and exception is None:
        fail(f"diagnostic question count exceeds hard maximum without exception in {path}")


def check_reusable_contract(marker: dict[str, Any]) -> None:
    for path in REQUIRED_REUSABLE_FILES:
        if not (ROOT / path).is_file():
            fail(f"missing required reusable file: {path}")
    if marker.get("generation_allowed") is not False:
        fail("template marker must set generation_allowed: false")

    setup = marker.get("instance_setup", {})
    expected_assets = {
        "agent_pilot_setup_guide": "docs/claude-agent-setup.md",
        "label_provisioning_workflow": ".github/workflows/ensure-repository-labels.yml",
        "instance_marker": INSTANCE_MARKER,
        "configuration_template": "study.config.example.yml",
    }
    for key, expected in expected_assets.items():
        if setup.get(key) != expected:
            fail(f"template marker {key} must reference {expected}")

    manifest = load_yaml("instructions/manifest.yml")
    if manifest.get("completion_contract") != COMPLETION_CONTRACT:
        fail(f"lifecycle manifest must reference {COMPLETION_CONTRACT}")
    phases = {phase.get("id"): phase for phase in manifest.get("phases", []) if isinstance(phase, dict)}
    if phases.get("intake", {}).get("next_phase") != "diagnostic":
        fail("intake phase must guide to diagnostic")
    diagnostic = phases.get("diagnostic", {})
    if diagnostic.get("next_phase") != "generate":
        fail("diagnostic phase must guide to generation")
    if diagnostic.get("merge_policy_path") != "workflow.diagnostic_merge_policy":
        fail("diagnostic phase must reference its merge policy")
    if diagnostic.get("outputs") != [INSTANCE_MARKER, DIAGNOSTIC_STATE]:
        fail("diagnostic phase must restrict outputs to marker and diagnostic summary")

    instance_template = load_yaml("templates/instance.yml")
    validate_workflow_policy(instance_template, required=True)
    workflow = instance_template.get("workflow", {})
    if workflow.get("intake_merge_policy") != "auto_when_unambiguous":
        fail("new instances must default intake to auto_when_unambiguous")
    if workflow.get("diagnostic_merge_policy") != "auto_when_unambiguous":
        fail("new instances must default diagnostic to auto_when_unambiguous")

    completion = load_text(COMPLETION_CONTRACT)
    for term in ["Next step", "Continue command", "Concision rule", "auto_when_unambiguous", "Do not send a separate transition message"]:
        if term not in completion:
            fail(f"phase completion contract is missing required term: {term}")


def check_template_mode(marker: dict[str, Any]) -> None:
    for path in INSTANCE_ARTIFACTS:
        if (ROOT / path).exists():
            fail(f"instance artifact must not exist before instance setup: {path}")
    print("Template-mode guard passed.")


def check_instance_mode(marker: dict[str, Any]) -> None:
    for path in INSTANCE_ARTIFACTS:
        if not (ROOT / path).exists():
            fail(f"required instance artifact is missing: {path}")
    instance = load_yaml(INSTANCE_MARKER)
    repository = instance.get("repository")
    canonical = marker.get("canonical_repository")
    if instance.get("kind") != "open-study-path-instance":
        fail("instance marker kind must be open-study-path-instance")
    if not isinstance(repository, str) or not repository.strip() or repository == "OWNER/REPOSITORY":
        fail("instance marker must contain a repository identifier")
    if repository == canonical:
        fail("canonical template repository cannot be configured as an instance")
    if instance.get("source_template") != canonical:
        fail("instance source_template must match the canonical repository")
    validate_workflow_policy(instance, required=False)
    if instance.get("status", {}).get("diagnostic_complete") is True and not (ROOT / DIAGNOSTIC_STATE).is_file():
        fail("completed diagnostic requires state/diagnostic-summary.json")
    print(f"Instance-mode guard passed for {repository}.")


def check_guard() -> None:
    marker = load_yaml(TEMPLATE_MARKER)
    check_reusable_contract(marker)
    check_instance_mode(marker) if is_instance() else check_template_mode(marker)


def option_values(field: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for option in field.get("options", []):
        if isinstance(option, str):
            values.add(option.lower())
        elif isinstance(option, dict) and isinstance(option.get("label"), str):
            values.add(option["label"].lower())
    return values


def check_intake() -> None:
    spec = load_yaml("intake/jotform-form-spec.yml")
    mapping = load_yaml("intake/field-mapping.yml")
    example = load_yaml("study.config.example.yml")
    issue_form = load_yaml(".github/ISSUE_TEMPLATE/create-study-path.yml")

    fields = [field for field in spec.get("fields", []) if isinstance(field, dict)]
    field_keys = [field.get("key") for field in fields]
    if len(field_keys) != len(set(field_keys)):
        fail("jotform specification contains duplicate field keys")
    missing = REQUIRED_INTAKE_KEYS.difference(field_keys)
    if missing:
        fail(f"jotform specification is missing required keys: {sorted(missing)}")
    removed = REMOVED_INTAKE_KEYS.intersection(field_keys)
    if removed:
        fail(f"jotform specification still contains removed intake keys: {sorted(removed)}")
    if spec.get("privacy", {}).get("attachments_optional") is not True or spec.get("privacy", {}).get("persist_raw_submission") is not False:
        fail("jotform privacy contract is invalid")

    language = next((field for field in fields if field.get("key") == "preferred_language"), {})
    if option_values(language) != {"pt-br", "en"}:
        fail("Jotform preferred language must offer exactly pt-BR and en")
    balance = next((field for field in fields if field.get("key") == "theory_practice_balance"), {})
    if balance.get("default") != "balanced":
        fail("Jotform theory/practice balance must default to balanced")
    task = next((field for field in fields if field.get("key") == "task_manager"), {})
    if not {"auto", "trello", "github_issues", "todoist"}.issubset(option_values(task)):
        fail("Jotform task manager must support auto, Trello, GitHub Issues and Todoist")
    routine = next((field for field in fields if field.get("key") == "study_routine_mode"), {})
    if option_values(routine) != {"none", "fixed_calendar", "flexible_reminders", "custom", "decide_later"}:
        fail("Jotform study routine must expose the supported routine modes")

    if mapping.get("spec_id") != spec.get("id") or mapping.get("version") != spec.get("version"):
        fail("field mapping identity does not match Jotform specification")
    mapped = set(mapping.get("mappings", {}))
    persistable = REQUIRED_INTAKE_KEYS - {"consent"}
    missing_mappings = persistable.difference(mapped)
    if missing_mappings:
        fail(f"field mapping is missing intake keys: {sorted(missing_mappings)}")
    stale = REMOVED_INTAKE_KEYS.intersection(mapped)
    if stale:
        fail(f"field mapping still contains removed intake keys: {sorted(stale)}")
    if "consent" in mapped:
        fail("consent must be validated but not persisted as course configuration")

    intake = example.get("intake", {})
    if intake.get("form_spec_id") != spec.get("id") or intake.get("form_spec_version") != spec.get("version"):
        fail("configuration example form specification identity is invalid")
    if intake.get("attachments_optional") is not True or intake.get("persist_raw_submission") is not False:
        fail("configuration example intake privacy contract is invalid")

    blocks = [block for block in issue_form.get("body", []) if isinstance(block, dict)]
    issue_ids = {block.get("id") for block in blocks if block.get("id")}
    issue_required = REQUIRED_INTAKE_KEYS - {"consent"}
    missing_issue = issue_required.difference(issue_ids)
    if missing_issue:
        fail(f"GitHub Issue Form is missing required fields: {sorted(missing_issue)}")
    if "consent" not in issue_ids:
        fail("GitHub Issue Form is missing required consent")
    removed_issue = REMOVED_INTAKE_KEYS.intersection(issue_ids)
    if removed_issue:
        fail(f"GitHub Issue Form still contains removed fields: {sorted(removed_issue)}")

    language_block = next((block for block in blocks if block.get("id") == "preferred_language"), {})
    attrs = language_block.get("attributes", {})
    if option_values(attrs) != {"português (brasil)", "english"} or attrs.get("default") != 0:
        fail("GitHub Issue Form language contract is invalid")
    task_block = next((block for block in blocks if block.get("id") == "task_manager"), {})
    task_options = option_values(task_block.get("attributes", {}))
    if not any("trello" in option for option in task_options) or not any("github issues" in option for option in task_options):
        fail("GitHub Issue Form task manager options are incomplete")
    routine_block = next((block for block in blocks if block.get("id") == "study_routine_mode"), {})
    routine_options = option_values(routine_block.get("attributes", {}))
    for term in ["sem lembretes", "horário fixo", "horário flexível", "própria rotina", "decidir depois"]:
        if not any(term in option for option in routine_options):
            fail(f"GitHub Issue Form routine options are missing: {term}")

    explanatory = "\n".join(str(block.get("attributes", {}).get("value", "")) for block in blocks if block.get("type") == "markdown")
    for term in ["GitHub", "fonte de verdade", "opcionais", CURRENT_INTAKE_MARKER]:
        if term not in explanatory:
            fail(f"GitHub Issue Form integration explanation is missing: {term}")
    print("Intake contract passed.")


def validate_config(path: str, validator: Draft202012Validator) -> None:
    errors = list(validator.iter_errors(load_yaml(path)))
    if errors:
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            print(f"SCHEMA ERROR in {path} at {location}: {error.message}", file=sys.stderr)
        raise SystemExit(1)


def validate_json_document(path: str, validator: Draft202012Validator) -> dict[str, Any]:
    document = load_json(path)
    errors = list(validator.iter_errors(document))
    if errors:
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "<root>"
            print(f"SCHEMA ERROR in {path} at {location}: {error.message}", file=sys.stderr)
        raise SystemExit(1)
    return document


def check_schema() -> None:
    study_validator = Draft202012Validator(load_json("schemas/study-config.schema.json"), format_checker=FormatChecker())
    validate_config("study.config.example.yml", study_validator)
    if is_instance():
        validate_config("study.config.yml", study_validator)
    diagnostic_validator = Draft202012Validator(load_json(DIAGNOSTIC_SCHEMA), format_checker=FormatChecker())
    template_document = validate_json_document(DIAGNOSTIC_TEMPLATE, diagnostic_validator)
    validate_diagnostic_budget(template_document, DIAGNOSTIC_TEMPLATE)
    if (ROOT / DIAGNOSTIC_STATE).is_file():
        validate_diagnostic_budget(validate_json_document(DIAGNOSTIC_STATE, diagnostic_validator), DIAGNOSTIC_STATE)
    print("Configuration and diagnostic schemas passed.")


CHECKS = {"yaml": check_yaml, "guard": check_guard, "intake": check_intake, "schema": check_schema}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=[*CHECKS, "all"])
    args = parser.parse_args()
    for check in CHECKS.values() if args.check == "all" else [CHECKS[args.check]]:
        check()
    print("Open Study Path repository validation passed.")


if __name__ == "__main__":
    main()
