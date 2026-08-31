#!/usr/bin/env python3
"""Regression coverage for deterministic intake completion recovery."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from review_framework import REVIEW_PROFILES, file_sha256, validate_changed_coverage

CONTRACT = "instructions/11-intake-completion-recovery.md"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def review_document(root: Path) -> dict:
    profile = REVIEW_PROFILES["intake"]
    artifacts = [
        ".open-study-path/instance.yml",
        "study.config.yml",
        "state/intake-summary.json",
    ]
    return {
        "contract_version": 1,
        "operation_id": "intake-issue-2-v1",
        "phase": "intake",
        "reviewer_role": profile["reviewer_role"],
        "independent_pass": True,
        "status": "approved",
        "reviewed_at": "2026-08-01T00:19:00-03:00",
        "artifacts": [
            {"path": path, "change": "current", "sha256": file_sha256(root / path)}
            for path in artifacts
        ],
        "checks": {
            "request_fidelity": "passed",
            "preference_preservation": "passed",
            "ambiguity_resolution": "passed",
            "data_minimization": "passed",
        },
        "blocking_findings": [],
        "non_blocking_findings": [],
    }


def main() -> None:
    contract = Path(CONTRACT).read_text(encoding="utf-8")
    required_terms = [
        "next_phase_consistency",
        "same pull request",
        "deterministic authoring defects",
        "validation is still running",
        "does not continue by itself",
        "Do not offer a passive wait as completion",
    ]
    for term in required_terms:
        if term not in contract:
            raise SystemExit(f"intake completion contract is missing: {term}")

    manifest = yaml.safe_load(Path("instructions/manifest.yml").read_text(encoding="utf-8"))
    intake = next(phase for phase in manifest["phases"] if phase["id"] == "intake")
    if intake.get("execution_contract") != CONTRACT:
        raise SystemExit("intake phase does not reference the completion recovery contract")

    with tempfile.TemporaryDirectory(prefix="open-study-path-intake-recovery-") as directory:
        root = Path(directory)
        write(root / ".open-study-path/instance.yml", "kind: open-study-path-instance\n")
        write(root / "study.config.yml", "configured: true\n")
        write(root / "state/intake-summary.json", "{}\n")
        review_path = "state/reviews/intake-issue-2-v1.yml"
        write(root / review_path, yaml.safe_dump(review_document(root), sort_keys=False))

        changed = [
            ".open-study-path/instance.yml",
            "study.config.yml",
            "state/intake-summary.json",
            review_path,
        ]
        failed = validate_changed_coverage(root, changed, instance_mode=True)
        if not any("next_phase_consistency" in error for error in failed.errors):
            raise SystemExit("missing intake next_phase_consistency was not detected")

        repaired = review_document(root)
        repaired["checks"]["next_phase_consistency"] = "passed"
        write(root / review_path, yaml.safe_dump(repaired, sort_keys=False))
        passed = validate_changed_coverage(root, changed, instance_mode=True)
        if passed.errors:
            raise SystemExit(f"deterministic intake review repair did not validate: {passed.errors}")

    print("Intake completion recovery regression passed.")


if __name__ == "__main__":
    main()
