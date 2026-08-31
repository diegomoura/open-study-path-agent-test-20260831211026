#!/usr/bin/env python3
"""Validate consistency from intake choices through active integration publication."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml

from integration_resolution import validate_documents

ROOT = Path(__file__).resolve().parents[1]


def fail(messages: list[str]) -> None:
    for message in messages:
        print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    return value if isinstance(value, dict) else {}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, dict) else {}


def validate_template_contract() -> None:
    required_files = [
        ROOT / "scripts" / "integration_resolution.py",
        ROOT / "scripts" / "test_integration_resolution.py",
        ROOT / "templates" / "integrations-state.json",
        ROOT / "instructions" / "42-integration-preflight.md",
        ROOT / "instructions" / "40-publish-tasks.md",
        ROOT / "scripts" / "lifecycle_next_action.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_files if not path.is_file()]
    if missing:
        fail([f"missing integration-resolution contract file: {path}" for path in missing])

    template_state = load_json(ROOT / "templates" / "integrations-state.json")
    resolution = template_state.get("resolution", {})
    if resolution != {
        "status": "not_started",
        "unresolved_capabilities": [],
        "validated_at": None,
    }:
        fail(["integration state template must initialize the resolution contract"])

    workflow = (ROOT / ".github" / "workflows" / "validate-template.yml").read_text(encoding="utf-8")
    for command in [
        "python scripts/test_integration_resolution.py",
        "python scripts/validate_integration_resolution.py",
    ]:
        if command not in workflow:
            fail([f"validation workflow is missing integration gate: {command}"])


def validate_instance() -> None:
    config_path = ROOT / "study.config.yml"
    state_path = ROOT / "state" / "integrations.json"
    plan_path = ROOT / "study" / "integrations.md"
    if not config_path.is_file() or not state_path.is_file():
        return

    config = load_yaml(config_path)
    state = load_json(state_path)
    plan = plan_path.read_text(encoding="utf-8") if plan_path.is_file() else ""
    result = validate_documents(config, state, plan)
    if result.errors:
        fail(list(result.errors))


def main() -> None:
    validate_template_contract()
    if (ROOT / ".open-study-path" / "instance.yml").is_file():
        validate_instance()
    print("Active integration selection and publication resolution passed.")


if __name__ == "__main__":
    main()
