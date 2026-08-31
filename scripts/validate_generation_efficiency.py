#!/usr/bin/env python3
"""Validate bounded connector-first generation execution."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import yaml

ROOT = Path(__file__).resolve().parents[1]
EXECUTION_CONTRACT = "instructions/32-generation-execution.md"
TERMINAL_RESOLVER = "scripts/generation_terminal_state.py"
TERMINAL_TESTS = "scripts/test_generation_terminal_state.py"
SCOPE_GUARD = "scripts/validate_instance_operation_scope.py"
SCOPE_TESTS = "scripts/test_instance_operation_scope.py"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr); raise SystemExit(1)


def text(path: str) -> str:
    target = ROOT / path
    if not target.is_file(): fail(f"missing generation-efficiency file: {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, terms: list[str]) -> None:
    content = text(path)
    for term in terms:
        if term not in content: fail(f"{path} is missing generation-efficiency term: {term}")


def forbid(path: str, terms: list[str]) -> None:
    content = text(path)
    for term in terms:
        if term in content: fail(f"{path} contains obsolete generation term: {term}")


def load_yaml(path: str) -> Any:
    return yaml.safe_load(text(path))


def main() -> None:
    require(EXECUTION_CONTRACT, [
        "Connector-first execution", "Do not attempt `gh`, `git clone`, `curl`", "Do not begin with shell authentication probes",
        "Do not use fixed `sleep` loops", "Capability preflight", "Batched GitHub writes", "create_blob", "create_tree",
        "create_commit", "update_ref", "never create one commit per generated file",
        "Never run `scripts/validate_curriculum.py` directly", "GitHub Actions is the final rendering environment",
        "scripts/validate_instance_operation_scope.py", "Do not change a validator to make generated content pass",
        "Batch every failure of the same deterministic class", TERMINAL_RESOLVER, "Final current-head read-back",
        "Never say that the trail is generated while the pull request remains open", "Terminal condition",
    ])
    require("AGENTS.md", [EXECUTION_CONTRACT, "Complete them before responding", "Do not lead with PR, CI", "instructions/57-materialize-next-content.md", "## Safety"])
    for path in [TERMINAL_RESOLVER, TERMINAL_TESTS, SCOPE_GUARD, SCOPE_TESTS]:
        text(path)
    manifest = load_yaml("instructions/manifest.yml")
    phases = {phase.get("id"): phase for phase in manifest.get("phases", []) if isinstance(phase, dict)}
    if phases.get("generate", {}).get("execution_contract") != EXECUTION_CONTRACT:
        fail("generate phase must reference the efficient execution contract")
    workflow = text(".github/workflows/validate-template.yml")
    for command in [
        "python scripts/test_instance_operation_scope.py", "python scripts/validate_instance_operation_scope.py",
        "python scripts/test_generation_terminal_state.py", "python scripts/validate_generation_efficiency.py",
        "python scripts/validate_learning_experience.py", "python scripts/test_curriculum_placeholder_detection.py",
        "python scripts/validate_curriculum_safe.py",
    ]:
        if command not in workflow: fail(f"validation workflow is missing: {command}")
    for term in ["REVIEW_BASE_SHA"]:
        if term not in workflow: fail(f"validation workflow is missing render/scope term: {term}")
    if "python scripts/validate_curriculum.py" in workflow:
        fail("workflow must use the safe curriculum validator")
    print("Efficient connector-first generation passed.")


if __name__ == "__main__":
    main()
