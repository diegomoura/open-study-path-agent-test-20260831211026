#!/usr/bin/env python3
"""Behavioral regressions for the agent-pilot auto-merge decision (Opcao C)."""

from __future__ import annotations

from pathlib import Path
import tempfile

import yaml

from agent_pilot_merge_decision import decide_merge
from review_framework import REVIEW_PROFILES, file_sha256


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def approved_review(root: Path, *, phase: str, artifacts: list[str]) -> str:
    profile = REVIEW_PROFILES[phase]
    relative = f"state/reviews/agent-pilot-{phase}.yml"
    document = {
        "contract_version": 1,
        "operation_id": f"agent-pilot-{phase}-v1",
        "phase": phase,
        "reviewer_role": profile["reviewer_role"],
        "independent_pass": True,
        "status": "approved",
        "reviewed_at": "2026-08-31T12:00:00Z",
        "artifacts": [
            {"path": path, "sha256": file_sha256(root / path)} for path in artifacts
        ],
        "checks": {check: "passed" for check in profile["checks"]},
        "blocking_findings": [],
        "non_blocking_findings": [],
    }
    write(root / relative, yaml.safe_dump(document, sort_keys=False))
    return relative


def action_required_review(root: Path, *, phase: str, artifacts: list[str]) -> str:
    profile = REVIEW_PROFILES[phase]
    relative = f"state/reviews/agent-pilot-{phase}.yml"
    document = {
        "contract_version": 1,
        "operation_id": f"agent-pilot-{phase}-v1",
        "phase": phase,
        "reviewer_role": profile["reviewer_role"],
        "independent_pass": True,
        "status": "action_required",
        "reviewed_at": "2026-08-31T12:00:00Z",
        "artifacts": [
            {"path": path, "sha256": file_sha256(root / path)} for path in artifacts
        ],
        "checks": {check: "passed" for check in profile["checks"]},
        "blocking_findings": ["something is wrong"],
        "non_blocking_findings": [],
    }
    write(root / relative, yaml.safe_dump(document, sort_keys=False))
    return relative


REQUIRED = frozenset({"ci-baseline-template", "ci-baseline-curriculum", "ci-intake"})


def test_merges_when_approved_and_all_required_checks_succeed() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "study.config.yml", "path: {}\n")
        review = approved_review(root, phase="intake", artifacts=["study.config.yml"])

        decision = decide_merge(
            root=root,
            review_relative_path=review,
            base_sha=None,
            required_job_ids=REQUIRED,
            job_results={
                "ci-baseline-template": "success",
                "ci-baseline-curriculum": "success",
                "ci-intake": "success",
                "ci-diagnostic": "skipped",  # not required for this phase -- irrelevant
            },
        )
        assert decision.should_merge, decision.reasons
        assert decision.reasons == ()


def test_blocks_when_reviewer_returned_action_required() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "study.config.yml", "path: {}\n")
        review = action_required_review(root, phase="intake", artifacts=["study.config.yml"])

        decision = decide_merge(
            root=root,
            review_relative_path=review,
            base_sha=None,
            required_job_ids=REQUIRED,
            job_results={
                "ci-baseline-template": "success",
                "ci-baseline-curriculum": "success",
                "ci-intake": "success",
            },
        )
        assert not decision.should_merge
        assert any("must be approved before merge" in reason for reason in decision.reasons)


def test_blocks_when_a_required_check_fails() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "study.config.yml", "path: {}\n")
        review = approved_review(root, phase="intake", artifacts=["study.config.yml"])

        decision = decide_merge(
            root=root,
            review_relative_path=review,
            base_sha=None,
            required_job_ids=REQUIRED,
            job_results={
                "ci-baseline-template": "success",
                "ci-baseline-curriculum": "success",
                "ci-intake": "failure",
            },
        )
        assert not decision.should_merge
        assert any("ci-intake" in reason for reason in decision.reasons)


def test_blocks_when_a_required_check_is_missing_entirely() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "study.config.yml", "path: {}\n")
        review = approved_review(root, phase="intake", artifacts=["study.config.yml"])

        decision = decide_merge(
            root=root,
            review_relative_path=review,
            base_sha=None,
            required_job_ids=REQUIRED,
            job_results={
                "ci-baseline-template": "success",
                "ci-baseline-curriculum": "success",
                # ci-intake never reported at all
            },
        )
        assert not decision.should_merge
        assert any("ci-intake" in reason for reason in decision.reasons)


def test_a_required_check_that_only_skipped_never_counts_as_passed() -> None:
    # A "skipped" result for a job this manifest phase genuinely requires must
    # block -- it must never be treated the same as a check that was correctly
    # not required for this phase in the first place.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "study.config.yml", "path: {}\n")
        review = approved_review(root, phase="intake", artifacts=["study.config.yml"])

        decision = decide_merge(
            root=root,
            review_relative_path=review,
            base_sha=None,
            required_job_ids=REQUIRED,
            job_results={
                "ci-baseline-template": "success",
                "ci-baseline-curriculum": "success",
                "ci-intake": "skipped",
            },
        )
        assert not decision.should_merge
        assert any("ci-intake" in reason for reason in decision.reasons)


def test_blocks_when_review_artifact_is_missing() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        decision = decide_merge(
            root=root,
            review_relative_path="state/reviews/agent-pilot-intake.yml",
            base_sha=None,
            required_job_ids=REQUIRED,
            job_results={
                "ci-baseline-template": "success",
                "ci-baseline-curriculum": "success",
                "ci-intake": "success",
            },
        )
        assert not decision.should_merge
        assert any("missing review artifact" in reason for reason in decision.reasons)


def main() -> None:
    test_merges_when_approved_and_all_required_checks_succeed()
    test_blocks_when_reviewer_returned_action_required()
    test_blocks_when_a_required_check_fails()
    test_blocks_when_a_required_check_is_missing_entirely()
    test_a_required_check_that_only_skipped_never_counts_as_passed()
    test_blocks_when_review_artifact_is_missing()
    print("Agent-pilot auto-merge decision regressions passed.")


if __name__ == "__main__":
    main()
