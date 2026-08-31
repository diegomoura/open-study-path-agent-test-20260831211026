#!/usr/bin/env python3
"""Shared review framework for generated Open Study Path artifacts.

The framework is intentionally PR-oriented: every generated artifact changed by
an instance operation must be covered by an approved review artifact changed in
the same pull request. Review artifacts bind the reviewer decision to exact
SHA-256 fingerprints, so a stale review cannot authorize a changed output.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import re
import subprocess
from typing import Any, Iterable, Mapping

import yaml

CONTRACT_VERSION = 1
APPROVED_STATUS = "approved"
PASSED = "passed"

REVIEW_PROFILES: dict[str, dict[str, Any]] = {
    "setup": {
        "reviewer_role": "setup_reviewer",
        "checks": (
            "repository_identity",
            "reusable_assets_preserved",
            "intake_entrypoint_ready",
            "safety_and_secrets",
            "next_phase_consistency",
        ),
    },
    "intake": {
        "reviewer_role": "intake_reviewer",
        "checks": (
            "request_fidelity",
            "preference_preservation",
            "ambiguity_resolution",
            "data_minimization",
            "next_phase_consistency",
        ),
    },
    "diagnostic": {
        "reviewer_role": "diagnostic_reviewer",
        "checks": (
            "evidence_basis",
            "bounded_questioning",
            "adjacent_experience_separation",
            "placement_consistency",
            "privacy_and_minimization",
        ),
    },
    "curriculum": {
        "reviewer_role": "curriculum_reviewer",
        "checks": (
            "scope_alignment",
            "dependency_integrity",
            "effort_feasibility",
            "learner_language",
            "content_review_complete",
            "assessment_alignment",
            "source_and_integration_consistency",
        ),
    },
    "publication": {
        "reviewer_role": "publication_reviewer",
        "checks": (
            "selected_capabilities_resolved",
            "external_projection_consistency",
            "idempotency_and_reuse",
            "learner_navigation",
            "privacy_cost_and_authority",
            "next_action_consistency",
        ),
    },
    "assessment": {
        "reviewer_role": "assessment_reviewer",
        "checks": (
            "submission_resolution",
            "rubric_fidelity",
            "independent_scoring",
            "feedback_alignment",
            "progress_update",
            "next_materialization_consistency",
        ),
    },
    "progress": {
        "reviewer_role": "progress_reviewer",
        "checks": (
            "source_state_consistency",
            "valid_state_transition",
            "external_projection_consistency",
            "next_action_consistency",
            "no_competing_authority",
        ),
    },
    "replan": {
        "reviewer_role": "replan_reviewer",
        "checks": (
            "evidence_trigger",
            "approved_scope_preservation",
            "dependency_revalidation",
            "version_and_review_refresh",
            "learner_impact_explained",
        ),
    },
    "migration": {
        "reviewer_role": "migration_reviewer",
        "checks": (
            "source_target_identity",
            "compatibility",
            "state_preservation",
            "idempotency",
            "rollback_and_failure_safety",
        ),
    },
}

REVIEW_PATH_PREFIX = "state/reviews/"
CONTENT_REVIEW_PATH_PREFIX = "state/content-reviews/"
INSTANCE_MARKER = ".open-study-path/instance.yml"

_OPERATION_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReviewValidation:
    path: str
    phase: str
    covered_artifacts: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class CoverageValidation:
    generated_changes: tuple[str, ...]
    covered_changes: tuple[str, ...]
    review_paths: tuple[str, ...]
    errors: tuple[str, ...]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_path(value: str) -> str:
    normalized = Path(value).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def base_file_sha256(root: Path, base_sha: str, relative_path: str) -> str | None:
    completed = subprocess.run(
        ["git", "show", f"{base_sha}:{relative_path}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        return None
    return sha256(completed.stdout).hexdigest()


def is_review_path(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized.startswith(REVIEW_PATH_PREFIX) and normalized.endswith((".yml", ".yaml"))


def is_generated_artifact(path: str) -> bool:
    """Return whether an instance PR output requires review coverage."""

    normalized = normalize_path(path)
    # Etapa 6a (docs/claude-agent-pilot-etapa6-design.md): a real track
    # dispatch's own review artifact failed CI over this exact file --
    # "generated artifacts are not covered by an approved current review:
    # state/agent-pilot-usage.jsonl" -- and the same gap was confirmed
    # already present, unnoticed, in the already-merged diagnostic PR
    # (state/agent-pilot-usage.jsonl was never listed in its `artifacts:`
    # either). It is the harness's own per-dispatch cost/token ledger,
    # appended by every phase's workflow step, not a domain artifact any
    # review profile's checks are about -- no profile's `checks` tuple has
    # anything to say about token usage. Excluding it here, at the
    # classification that every profile shares, fixes this for every phase
    # at once instead of asking each phase's reviewer prompt to remember to
    # declare a file it has no judgment to offer on.
    if normalized == "state/agent-pilot-usage.jsonl":
        return False
    if normalized in {INSTANCE_MARKER, "study.config.yml", "README.md"}:
        return True
    if normalized.startswith(REVIEW_PATH_PREFIX) or normalized.startswith(CONTENT_REVIEW_PATH_PREFIX):
        return False
    if normalized.startswith("study/") or normalized.startswith("state/"):
        return True
    if normalized == ".github/ISSUE_TEMPLATE/create-study-path.yml":
        return True
    if normalized.startswith(".github/ISSUE_TEMPLATE/assessment-topic-") and normalized.endswith(".yml"):
        return True
    return False


def phase_allows_artifact(phase: str, path: str) -> bool:
    normalized = normalize_path(path)
    if phase == "migration":
        return is_generated_artifact(normalized)
    if phase == "setup":
        return normalized in {
            INSTANCE_MARKER,
            "study.config.yml",
            "state/intake-summary.json",
            "state/progress.json",
            "state/integrations.json",
            "study/roadmap.md",
            "README.md",
        }
    if phase == "intake":
        return normalized in {
            INSTANCE_MARKER,
            "study.config.yml",
            "state/intake-summary.json",
        }
    if phase == "diagnostic":
        return normalized in {
            INSTANCE_MARKER,
            "state/diagnostic-summary.json",
        }
    if phase == "curriculum":
        return (
            normalized in {INSTANCE_MARKER, "study.config.yml"}
            or normalized.startswith("study/")
            or (
                normalized.startswith(".github/ISSUE_TEMPLATE/assessment-topic-")
                and normalized.endswith(".yml")
            )
        )
    if phase == "publication":
        return (
            normalized in {
                "study.config.yml",
                "study/integrations.md",
                "state/integrations.json",
            }
            or normalized.startswith("study/modules/")
            or normalized.startswith("state/operations/")
        )
    if phase == "assessment":
        return (
            normalized in {
                "state/progress.json",
                "state/integrations.json",
                "study/roadmap.md",
                "study/integrations.md",
            }
            or normalized.startswith("state/assessments/")
            or normalized.startswith("study/topics/")
            or normalized.startswith("study/modules/")
            or normalized.startswith("study/flashcards/")
            or normalized.startswith("study/assessments/")
            or normalized.startswith("state/operations/")
            or (
                normalized.startswith(".github/ISSUE_TEMPLATE/assessment-topic-")
                and normalized.endswith(".yml")
            )
        )
    if phase == "progress":
        return normalized in {"state/progress.json", "state/integrations.json"} or normalized.startswith(
            "state/operations/"
        )
    if phase == "replan":
        return (
            normalized in {
                INSTANCE_MARKER,
                "study.config.yml",
                "state/progress.json",
            }
            or normalized.startswith("study/")
            or (
                normalized.startswith(".github/ISSUE_TEMPLATE/assessment-topic-")
                and normalized.endswith(".yml")
            )
        )
    return False


def changed_files(root: Path, base_sha: str | None, head_sha: str = "HEAD") -> tuple[str, ...]:
    if not base_sha:
        return ()
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "could not calculate review coverage diff; "
            f"git exited {completed.returncode}: {completed.stderr.strip()}"
        )
    return tuple(
        sorted(
            {
                normalize_path(line)
                for line in completed.stdout.splitlines()
                if line.strip()
            }
        )
    )


def validate_review_document(
    root: Path,
    relative_path: str,
    *,
    base_sha: str | None = None,
) -> ReviewValidation:
    path = root / relative_path
    errors: list[str] = []
    if not path.is_file():
        return ReviewValidation(relative_path, "", (), (f"missing review artifact: {relative_path}",))

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive parser reporting
        return ReviewValidation(relative_path, "", (), (f"invalid YAML in {relative_path}: {exc}",))

    if not isinstance(document, dict):
        return ReviewValidation(relative_path, "", (), (f"review artifact must be an object: {relative_path}",))

    phase = str(document.get("phase") or "").strip()
    profile = REVIEW_PROFILES.get(phase)
    if not profile:
        errors.append(f"{relative_path} has unknown review phase: {phase or '<missing>'}")

    if document.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"{relative_path} must use contract_version {CONTRACT_VERSION}")

    operation_id = str(document.get("operation_id") or "").strip()
    if not _OPERATION_ID.fullmatch(operation_id):
        errors.append(f"{relative_path} has invalid operation_id: {operation_id or '<missing>'}")

    if profile and document.get("reviewer_role") != profile["reviewer_role"]:
        errors.append(f"{relative_path} reviewer_role must be {profile['reviewer_role']}")

    if document.get("independent_pass") is not True:
        errors.append(f"{relative_path} must record independent_pass: true")

    if document.get("status") != APPROVED_STATUS:
        errors.append(f"{relative_path} must be approved before merge")

    reviewed_at = str(document.get("reviewed_at") or "").strip()
    if not reviewed_at:
        errors.append(f"{relative_path} is missing reviewed_at")

    blocking = _list(document.get("blocking_findings"))
    if blocking:
        errors.append(f"{relative_path} cannot be approved with blocking_findings")

    non_blocking = document.get("non_blocking_findings")
    if not isinstance(non_blocking, list):
        errors.append(f"{relative_path} non_blocking_findings must be a list")

    checks = _mapping(document.get("checks"))
    if profile:
        for check in profile["checks"]:
            if checks.get(check) != PASSED:
                errors.append(f"{relative_path} required check is not passed: {check}")

    artifacts = _list(document.get("artifacts"))
    if not artifacts:
        errors.append(f"{relative_path} must list reviewed artifacts")

    covered: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(artifacts):
        if not isinstance(entry, dict):
            errors.append(f"{relative_path} artifact #{index + 1} must be an object")
            continue

        artifact_path = normalize_path(str(entry.get("path") or ""))
        change = str(entry.get("change") or "current").strip().lower()
        digest = str(entry.get("sha256") or "").strip().lower()
        previous_digest = str(entry.get("previous_sha256") or "").strip().lower()

        if not artifact_path:
            errors.append(f"{relative_path} artifact #{index + 1} is missing path")
            continue
        if artifact_path in seen:
            errors.append(f"{relative_path} lists duplicate artifact: {artifact_path}")
            continue
        seen.add(artifact_path)
        if is_review_path(artifact_path):
            errors.append(f"{relative_path} cannot review itself or another generic review artifact: {artifact_path}")
            continue
        if profile and not phase_allows_artifact(phase, artifact_path):
            errors.append(
                f"{relative_path} profile {phase} cannot approve out-of-scope artifact: {artifact_path}"
            )
            continue

        target = root / artifact_path

        if change == "deleted":
            if target.exists():
                errors.append(f"{relative_path} marks an existing artifact as deleted: {artifact_path}")
                continue
            if not _SHA256.fullmatch(previous_digest):
                errors.append(f"{relative_path} has invalid previous_sha256 for deleted artifact {artifact_path}")
                continue
            if not base_sha:
                errors.append(f"{relative_path} cannot verify deleted artifact without REVIEW_BASE_SHA: {artifact_path}")
                continue
            actual_previous = base_file_sha256(root, base_sha, artifact_path)
            if actual_previous is None:
                errors.append(f"{relative_path} cannot find deleted artifact in review base: {artifact_path}")
                continue
            if actual_previous != previous_digest:
                errors.append(
                    f"{relative_path} has stale deletion evidence for {artifact_path}: "
                    f"expected {actual_previous}, recorded {previous_digest}"
                )
                continue
            covered.append(artifact_path)
            continue

        if change != "current":
            errors.append(f"{relative_path} has invalid change type for {artifact_path}: {change}")
            continue
        if not target.is_file():
            errors.append(f"{relative_path} references missing artifact: {artifact_path}")
            continue
        if not _SHA256.fullmatch(digest):
            errors.append(f"{relative_path} has invalid sha256 for {artifact_path}")
            continue
        actual = file_sha256(target)
        if actual != digest:
            errors.append(f"{relative_path} is stale for {artifact_path}: expected {actual}, recorded {digest}")
            continue
        covered.append(artifact_path)

    return ReviewValidation(relative_path, phase, tuple(sorted(covered)), tuple(errors))


def validate_changed_coverage(
    root: Path,
    paths: Iterable[str],
    *,
    instance_mode: bool,
    base_sha: str | None = None,
) -> CoverageValidation:
    normalized_paths = tuple(sorted({normalize_path(path) for path in paths}))
    changed_reviews = tuple(path for path in normalized_paths if is_review_path(path))
    generated = tuple(path for path in normalized_paths if is_generated_artifact(path)) if instance_mode else ()

    errors: list[str] = []
    covered: set[str] = set()
    for review_path in changed_reviews:
        result = validate_review_document(root, review_path, base_sha=base_sha)
        errors.extend(result.errors)
        covered.update(result.covered_artifacts)

    if generated and not changed_reviews:
        errors.append("generated instance artifacts changed without an independent review artifact under state/reviews/")

    missing = sorted(set(generated) - covered)
    if missing:
        errors.append("generated artifacts are not covered by an approved current review: " + ", ".join(missing))

    return CoverageValidation(
        generated_changes=tuple(generated),
        covered_changes=tuple(sorted(set(generated).intersection(covered))),
        review_paths=changed_reviews,
        errors=tuple(errors),
    )


def validate_current_pr(root: Path, base_sha: str | None = None) -> CoverageValidation:
    resolved_base = base_sha or os.getenv("REVIEW_BASE_SHA") or None
    paths = changed_files(root, resolved_base)
    instance_mode = (root / INSTANCE_MARKER).is_file()
    return validate_changed_coverage(
        root,
        paths,
        instance_mode=instance_mode,
        base_sha=resolved_base,
    )
