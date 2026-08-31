#!/usr/bin/env python3
"""Validate the optional per-agent model configuration.

Stage 1 of the multi-agent work proposal: this only validates the schema and
prints the resolved (tier, model) per agent plus any non-blocking structural
warnings. It does not call any API and does not write to state/reviews/ yet --
that wiring happens once real agent workflows exist (stage 2+).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from agent_model_resolution import AGENT_CATALOG, resolve_effective_models, structural_warnings

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "agent-model-config.schema.json"
TEMPLATE_PATH = ROOT / "templates" / "agent-models.yml"
INSTANCE_PATH = ROOT / ".open-study-path" / "models.yml"


def fail(messages: list[str]) -> None:
    for message in messages:
        print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    return value if isinstance(value, dict) else {}


def load_json(path: Path) -> dict[str, Any]:
    import json

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_template_contract() -> None:
    required_files = [
        ROOT / "scripts" / "agent_model_resolution.py",
        ROOT / "scripts" / "test_agent_model_resolution.py",
        ROOT / "schemas" / "agent-model-config.schema.json",
        ROOT / "templates" / "agent-models.yml",
        ROOT / "docs" / "agent-model-configuration.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_files if not path.is_file()]
    if missing:
        fail([f"missing agent-model-config contract file: {path}" for path in missing])


def validate_document(path: Path, validator: Draft202012Validator) -> dict[str, Any]:
    document = load_yaml(path)
    errors = sorted(validator.iter_errors(document), key=lambda error: error.path)
    if errors:
        fail([f"{path.relative_to(ROOT)}: {error.message}" for error in errors])
    return document


def report(label: str, document: dict[str, Any]) -> None:
    resolved = resolve_effective_models(document)
    print(f"{label}: {len(resolved)} agents resolved (reasoning_tier={document.get('reasoning_tier')})")
    for agent_id in sorted(resolved):
        agent = resolved[agent_id]
        print(f"  - {agent.agent_id}: {agent.effective_tier} ({agent.source}) -> {agent.model}")
    for warning in structural_warnings(resolved):
        print(f"WARN: {warning}")


def main() -> None:
    validate_template_contract()

    validator = Draft202012Validator(load_json(SCHEMA_PATH), format_checker=FormatChecker())

    template_document = validate_document(TEMPLATE_PATH, validator)
    unknown_defaults = set(template_document.get("model_overrides", {})) - set(AGENT_CATALOG)
    if unknown_defaults:
        fail([f"templates/agent-models.yml references unknown agent id: {name}" for name in sorted(unknown_defaults)])
    if any(template_document.get("model_overrides", {}).values()):
        fail(["templates/agent-models.yml must ship with every override set to null (recommended tier)"])
    report("Template default", template_document)

    if INSTANCE_PATH.is_file():
        instance_document = validate_document(INSTANCE_PATH, validator)
        report("Instance", instance_document)

    print("Agent model configuration passed.")


if __name__ == "__main__":
    main()
