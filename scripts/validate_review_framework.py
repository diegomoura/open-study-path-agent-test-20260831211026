#!/usr/bin/env python3
"""Validate reusable review contracts and instance PR review coverage."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml

from generated_instance_contract import is_specialized_review_path
from review_framework import REVIEW_PROFILES, changed_files, validate_changed_coverage
from review_framework_guard import (
    instance_transition_errors,
    review_path_errors,
    review_phases,
)

ROOT = Path(__file__).resolve().parents[1]
INSTANCE_MARKER = ".open-study-path/instance.yml"
REVIEW_INSTRUCTION = "instructions/04-review-generated-artifacts.md"
REVIEW_DOC = "docs/review-framework.md"
REVIEW_TEMPLATE = "templates/review.yml"
OPERATION_PREFIX = "state/operations/"

LIFECYCLE_PHASE_PROFILES = {
    "bootstrap_instance": "setup",
    "configure_intake": "setup",
    "intake": "intake",
    "diagnostic": "diagnostic",
    "generate": "curriculum",
    "publish": "publication",
    "evaluate": "assessment",
    "track": "progress",
    "replan": "replan",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        fail(f"missing review-framework file: {path}")
    return target.read_text(encoding="utf-8")


def load_yaml(path: str) -> Any:
    return yaml.safe_load(read(path))


def review_enabled(document: Any) -> bool:
    if not isinstance(document, dict):
        return False
    framework = document.get("review_framework")
    return isinstance(framework, dict) and framework.get("enabled") is True


def load_instance_from_base(base_sha: str | None) -> Any:
    if not base_sha:
        return None
    completed = subprocess.run(
        ["git", "show", f"{base_sha}:{INSTANCE_MARKER}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    try:
        return yaml.safe_load(completed.stdout)
    except yaml.YAMLError as exc:
        fail(
            f"could not parse base instance marker for review enforcement: {exc}"
        )


def uses_dedicated_validation(path: str) -> bool:
    """Return technical evidence paths governed by their own validators."""

    normalized = Path(path).as_posix()
    return is_specialized_review_path(normalized) or (
        normalized.startswith(OPERATION_PREFIX) and normalized.endswith(".json")
    )


def validate_reusable_contract() -> None:
    for path in [
        REVIEW_INSTRUCTION,
        REVIEW_DOC,
        REVIEW_TEMPLATE,
        "scripts/generated_instance_contract.py",
        "scripts/validate_task_projection.py",
    ]:
        read(path)

    instance_template = load_yaml("templates/instance.yml")
    if not isinstance(instance_template, dict):
        fail("templates/instance.yml must be an object")
    framework = instance_template.get("review_framework")
    if not isinstance(framework, dict):
        fail("new instances must define review_framework")
    if framework.get("contract_version") != 1:
        fail("review_framework.contract_version must be 1")
    if framework.get("enabled") is not True:
        fail("new instances must enable the review framework")
    if framework.get("independent_pass") is not True:
        fail("new instances must require an independent review pass")
    if framework.get("require_generated_diff_coverage") is not True:
        fail("new instances must require generated diff coverage")
    required_profiles = framework.get("required_profiles")
    if not isinstance(required_profiles, list) or set(required_profiles) != set(
        REVIEW_PROFILES
    ):
        fail(
            "review_framework.required_profiles must list every supported profile"
        )

    manifest = load_yaml("instructions/manifest.yml")
    phases = {
        phase.get("id"): phase
        for phase in manifest.get("phases", [])
        if isinstance(phase, dict)
    }
    for phase_id, profile in LIFECYCLE_PHASE_PROFILES.items():
        phase = phases.get(phase_id)
        if not phase:
            fail(f"lifecycle manifest is missing phase: {phase_id}")
        if phase.get("phase_review") != REVIEW_INSTRUCTION:
            fail(
                f"{phase_id} must reference the shared phase review instruction"
            )
        if phase.get("review_profile") != profile:
            fail(f"{phase_id} must use review_profile: {profile}")
        if phase.get("review_outputs") != ["state/reviews/"]:
            fail(
                f"{phase_id} must declare state/reviews/ as dedicated review output"
            )
        outputs = phase.get("outputs", [])
        if "state/reviews/" in outputs:
            fail(
                f"{phase_id} must keep review evidence separate from phase outputs"
            )

    review_template = load_yaml(REVIEW_TEMPLATE)
    if not isinstance(review_template, dict):
        fail("templates/review.yml must be an object")
    for key in [
        "contract_version",
        "operation_id",
        "phase",
        "reviewer_role",
        "independent_pass",
        "status",
        "reviewed_at",
        "artifacts",
        "checks",
        "blocking_findings",
        "non_blocking_findings",
    ]:
        if key not in review_template:
            fail(f"templates/review.yml is missing key: {key}")

    workflow = read(".github/workflows/validate-template.yml")
    for term in [
        "fetch-depth: 0",
        "REVIEW_BASE_SHA:",
        "github.event.before",
        "python scripts/test_review_framework.py",
        "python scripts/validate_review_framework.py",
    ]:
        if term not in workflow:
            fail(
                f"validation workflow is missing review-framework term: {term}"
            )

    agents = read("AGENTS.md")
    for term in [
        REVIEW_DOC,
        REVIEW_INSTRUCTION,
        "Every generated artifact changed by an instance operation",
        "state/reviews/",
    ]:
        if term not in agents:
            fail(f"AGENTS.md is missing review-framework term: {term}")

    completion = read("instructions/phase-completion.md")
    for term in [
        REVIEW_INSTRUCTION,
        "approved review artifact",
        "generated diff coverage",
    ]:
        if term not in completion:
            fail(f"phase completion is missing review-framework term: {term}")


def validate_instance_diff() -> None:
    base_sha = os.getenv("REVIEW_BASE_SHA") or None
    head_marker = ROOT / INSTANCE_MARKER
    head_document = (
        yaml.safe_load(head_marker.read_text(encoding="utf-8"))
        if head_marker.is_file()
        else None
    )
    base_document = load_instance_from_base(base_sha)

    # A reviewed instance cannot disable the gate by deleting its marker. Legacy
    # instances remain compatible until review_framework is explicitly enabled.
    if not review_enabled(head_document) and not review_enabled(base_document):
        return

    paths = changed_files(ROOT, base_sha)
    preflight_errors = [
        *review_path_errors(ROOT, paths),
        *instance_transition_errors(
            base_document=base_document,
            head_document=head_document,
            head_marker_exists=head_marker.is_file(),
            changed_review_phases=review_phases(ROOT, paths),
        ),
    ]
    if preflight_errors:
        for error in preflight_errors:
            print(f"REVIEW ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)

    # Specialized review evidence and operation journals are validated by their
    # dedicated contracts. Requiring generic phase coverage creates circular
    # evidence or conflicts with the lifecycle manifest.
    coverage_paths = tuple(
        path for path in paths if not uses_dedicated_validation(path)
    )
    result = validate_changed_coverage(
        ROOT,
        coverage_paths,
        instance_mode=True,
        base_sha=base_sha,
    )
    if result.errors:
        for error in result.errors:
            print(f"REVIEW ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    validate_reusable_contract()
    validate_instance_diff()
    print("Independent generated-artifact review framework passed.")


if __name__ == "__main__":
    main()
