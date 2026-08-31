#!/usr/bin/env python3
"""Validate first-chat setup discovery, transport, metadata readiness and marker preservation."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SETUP_EXECUTION = "instructions/02-setup-execution.md"
CURRENT_INTAKE_MARKER = "<!-- open-study-path:intake form_id=create-study-path version=4 -->"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def text(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        fail(f"missing setup-safety file: {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, terms: list[str]) -> None:
    content = text(path)
    for term in terms:
        if term not in content:
            fail(f"{path} is missing setup-safety term: {term}")


def run_validator(repo: Path, check: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/validate_template.py", check],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def materialize_minimal_instance(repo: Path) -> None:
    instance = (repo / "templates/instance.yml").read_text(encoding="utf-8")
    instance = instance.replace("OWNER/REPOSITORY", "example/setup-regression")
    (repo / ".open-study-path/instance.yml").write_text(instance, encoding="utf-8")

    shutil.copy2(repo / "study.config.example.yml", repo / "study.config.yml")

    state_dir = repo / "state"
    state_dir.mkdir(exist_ok=True)
    shutil.copy2(repo / "templates/state/intake-summary.json", state_dir / "intake-summary.json")
    shutil.copy2(repo / "templates/state/progress.json", state_dir / "progress.json")

    integrations = (repo / "templates/integrations-state.json").read_text(encoding="utf-8")
    integrations = integrations.replace("OWNER/REPOSITORY", "example/setup-regression")
    (state_dir / "integrations.json").write_text(integrations, encoding="utf-8")

    shutil.copy2(repo / "templates/agent-models.yml", repo / ".open-study-path/models.yml")

    study_dir = repo / "study"
    study_dir.mkdir(exist_ok=True)
    shutil.copy2(repo / "templates/roadmap.md", study_dir / "roadmap.md")


def validate_intake_metadata_schema() -> None:
    schema = json.loads(text("schemas/study-config.schema.json"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    config = yaml.safe_load(text("study.config.example.yml"))
    config["intake"].update(
        {
            "provider": "github_issue",
            "setup_status": "ready",
            "form_id": "create-study-path",
            "form_url": "https://github.com/example/course/issues/new?template=create-study-path.yml",
            "created_by": "reused_existing",
            "submission_strategy": "unique_verified_candidate",
        }
    )

    valid_errors = list(validator.iter_errors(config))
    if valid_errors:
        details = "; ".join(error.message for error in valid_errors)
        fail(f"canonical GitHub intake metadata must satisfy the schema: {details}")

    obsolete_strategy = copy.deepcopy(config)
    obsolete_strategy["intake"]["submission_strategy"] = "latest_approved"
    if not list(validator.iter_errors(obsolete_strategy)):
        fail("schema accepted obsolete newest-issue submission strategy")

    false_creator = copy.deepcopy(config)
    false_creator["intake"]["created_by"] = "instance_owner"
    if not list(validator.iter_errors(false_creator)):
        fail("schema accepted instance_owner for the inherited GitHub Issue Form")

    strategy_enum = schema["properties"]["intake"]["properties"]["submission_strategy"]["enum"]
    if "unique_verified_candidate" not in strategy_enum:
        fail("schema must expose unique_verified_candidate")
    if "latest_approved" in strategy_enum:
        fail("schema must not expose latest_approved")


def validate_contracts() -> None:
    require(SETUP_EXECUTION, [
        "Connector-first repository access",
        "do not test `gh` availability",
        "do not inspect environment variables for GitHub tokens",
        "do not run `git clone`",
        "Repository metadata",
        ".open-study-path/template.yml",
        "Do not reconstruct the repository",
        "Verify intake repository metadata",
        CURRENT_INTAKE_MARKER,
        "study-request",
        "intake:imported",
        "scripts/ensure_repository_labels.py",
        "Allowed setup diff",
        "Mandatory atomic publication",
        "Create one feature branch before writing any generated setup artifact",
        "Publish the complete setup in one commit",
        "Never write generated setup artifacts directly to the default branch",
        "Open exactly one setup pull request",
        "Intermediate branch commits are implementation details",
        "same unchanged complete head",
        "failing, pending, cancelled, missing or unreadable required check",
        "Do not claim that the instance is configured",
    ])
    require("AGENTS.md", [
        SETUP_EXECUTION,
        "Repository metadata",
        "retains `.open-study-path/template.yml`",
        "current repository form contract marker",
        "study-request",
        "intake:imported",
        "Never ask the learner to edit an issue to add a technical marker",
        "CI is red or unknown",
    ])
    require("instructions/00-bootstrap.md", [
        SETUP_EXECUTION,
        "sentinel files",
        "create one feature branch",
        "Never write setup artifacts directly to the default branch",
        "Keep `.open-study-path/template.yml`",
        "Open exactly one pull request",
        "merge gate",
        "templates/agent-models.yml",
        ".open-study-path/models.yml",
        "Never overwrite an existing `.open-study-path/models.yml`",
    ])
    require("instructions/05-configure-intake.md", [
        SETUP_EXECUTION,
        "Do not infer absence from repository size",
        CURRENT_INTAKE_MARKER,
        "scripts/ensure_repository_labels.py",
        "created_by: reused_existing",
        "submission_strategy: unique_verified_candidate",
        "Never select the newest issue",
        "submitted issue does not contain the form marker",
        "Do not edit, recreate or replace it",
        "failing, pending, cancelled, missing or unreadable",
    ])
    require("instructions/phase-completion.md", [
        "current unchanged pull-request head",
        "cannot be verified",
        "Do not merge and do not send a successful phase response",
    ])
    require("docs/validation-modes.md", [
        "repository metadata",
        "must remain present",
        "takes precedence",
    ])

    validate_intake_metadata_schema()

    manifest = yaml.safe_load(text("instructions/manifest.yml"))
    phases = {
        phase.get("id"): phase
        for phase in manifest.get("phases", [])
        if isinstance(phase, dict)
    }
    for phase_id in ["bootstrap_instance", "configure_intake"]:
        if phases.get(phase_id, {}).get("execution_contract") != SETUP_EXECUTION:
            fail(f"{phase_id} must reference {SETUP_EXECUTION}")

    validation_workflow = text(".github/workflows/validate-template.yml")
    if "python scripts/validate_setup_safety.py" not in validation_workflow:
        fail("validation workflow must run setup-safety regression")
    for command in [
        "python scripts/test_intake_resolution.py",
        "python scripts/test_repository_labels.py",
    ]:
        if command not in validation_workflow:
            fail(f"validation workflow must run: {command}")

    setup_workflow = text(".github/workflows/ensure-repository-labels.yml")
    for term in [
        "issues: write",
        "Ensure intake labels",
        "scripts/ensure_repository_labels.py",
        '--repository "$GITHUB_REPOSITORY"',
    ]:
        if term not in setup_workflow:
            fail(f"setup workflow is missing intake metadata provisioning: {term}")


def validate_instance_regression() -> None:
    with tempfile.TemporaryDirectory(prefix="open-study-path-setup-") as temporary:
        repo = Path(temporary) / "repo"
        shutil.copytree(
            ROOT,
            repo,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
        )
        materialize_minimal_instance(repo)

        template_marker = repo / ".open-study-path/template.yml"
        instance_marker = repo / ".open-study-path/instance.yml"
        if not template_marker.is_file() or not instance_marker.is_file():
            fail("a configured instance must retain both repository markers")

        models_config = repo / ".open-study-path/models.yml"
        if not models_config.is_file():
            fail("bootstrap must copy templates/agent-models.yml into .open-study-path/models.yml")

        valid = run_validator(repo, "all")
        if valid.returncode != 0:
            details = (valid.stdout + valid.stderr).strip()
            fail(f"safe template-to-instance setup did not validate: {details}")

        template_marker.unlink()
        destructive = run_validator(repo, "yaml")
        combined = destructive.stdout + destructive.stderr
        if destructive.returncode == 0:
            fail("validator accepted an instance that deleted the template marker")
        if "missing required YAML file: .open-study-path/template.yml" not in combined:
            fail("template-marker deletion failed for an unexpected reason")


def main() -> None:
    validate_contracts()
    validate_instance_regression()
    print("Connector-first atomic setup, deterministic intake metadata and marker preservation passed.")


if __name__ == "__main__":
    main()
