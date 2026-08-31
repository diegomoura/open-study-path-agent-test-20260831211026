#!/usr/bin/env python3
"""Regression tests for the shared generated-artifact review framework."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile

import yaml

from review_framework import (
    REVIEW_PROFILES,
    file_sha256,
    is_generated_artifact,
    validate_changed_coverage,
)
from review_framework_guard import (
    instance_transition_errors,
    review_path_errors,
)
from validate_review_framework import uses_dedicated_validation


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def approved_review(
    root: Path, *, phase: str, artifacts: list[str], blocking=None
) -> str:
    profile = REVIEW_PROFILES[phase]
    relative = f"state/reviews/{phase}.yml"
    document = {
        "contract_version": 1,
        "operation_id": f"{phase}-review-v1",
        "phase": phase,
        "reviewer_role": profile["reviewer_role"],
        "independent_pass": True,
        "status": "approved",
        "reviewed_at": "2026-07-30T12:00:00Z",
        "artifacts": [
            {"path": path, "sha256": file_sha256(root / path)}
            for path in artifacts
        ],
        "checks": {check: "passed" for check in profile["checks"]},
        "blocking_findings": blocking or [],
        "non_blocking_findings": [],
    }
    write(root / relative, yaml.safe_dump(document, sort_keys=False))
    return relative


def test_valid_intake_review() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(
            root / ".open-study-path/instance.yml",
            "kind: open-study-path-instance\n",
        )
        write(root / "study.config.yml", "path: {}\n")
        write(root / "state/intake-summary.json", "{}\n")
        review = approved_review(
            root,
            phase="intake",
            artifacts=[
                ".open-study-path/instance.yml",
                "study.config.yml",
                "state/intake-summary.json",
            ],
        )
        result = validate_changed_coverage(
            root,
            [
                ".open-study-path/instance.yml",
                "study.config.yml",
                "state/intake-summary.json",
                review,
            ],
            instance_mode=True,
        )
        assert not result.errors, result.errors
        assert len(result.covered_changes) == 3


def test_missing_review_blocks_generated_change() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(
            root / ".open-study-path/instance.yml",
            "kind: open-study-path-instance\n",
        )
        write(root / "study/roadmap.md", "# Roadmap\n")
        result = validate_changed_coverage(
            root, ["study/roadmap.md"], instance_mode=True
        )
        assert any(
            "without an independent review artifact" in error
            for error in result.errors
        )
        assert any("study/roadmap.md" in error for error in result.errors)


def test_stale_hash_blocks_review() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(
            root / ".open-study-path/instance.yml",
            "kind: open-study-path-instance\n",
        )
        write(
            root / "state/integrations.json",
            '{"sync":{"status":"success"}}\n',
        )
        review = approved_review(
            root,
            phase="publication",
            artifacts=["state/integrations.json"],
        )
        write(
            root / "state/integrations.json",
            '{"sync":{"status":"failed"}}\n',
        )
        result = validate_changed_coverage(
            root,
            ["state/integrations.json", review],
            instance_mode=True,
        )
        assert any("is stale" in error for error in result.errors)


def test_blocking_finding_prevents_approval() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(
            root / ".open-study-path/instance.yml",
            "kind: open-study-path-instance\n",
        )
        write(root / "state/diagnostic-summary.json", "{}\n")
        review = approved_review(
            root,
            phase="diagnostic",
            artifacts=["state/diagnostic-summary.json"],
            blocking=["Placement conclusion is unsupported."],
        )
        result = validate_changed_coverage(
            root,
            ["state/diagnostic-summary.json", review],
            instance_mode=True,
        )
        assert any("blocking_findings" in error for error in result.errors)


def test_required_check_cannot_be_skipped() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(
            root / ".open-study-path/instance.yml",
            "kind: open-study-path-instance\n",
        )
        write(root / "state/progress.json", "{}\n")
        review = approved_review(
            root, phase="progress", artifacts=["state/progress.json"]
        )
        document = yaml.safe_load(
            (root / review).read_text(encoding="utf-8")
        )
        document["checks"]["next_action_consistency"] = "pending"
        write(root / review, yaml.safe_dump(document, sort_keys=False))
        result = validate_changed_coverage(
            root, ["state/progress.json", review], instance_mode=True
        )
        assert any(
            "next_action_consistency" in error for error in result.errors
        )


def test_review_must_cover_every_generated_change() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(
            root / ".open-study-path/instance.yml",
            "kind: open-study-path-instance\n",
        )
        write(root / "study/roadmap.md", "# Roadmap\n")
        write(root / "study/integrations.md", "# Integrations\n")
        review = approved_review(
            root, phase="curriculum", artifacts=["study/roadmap.md"]
        )
        result = validate_changed_coverage(
            root,
            ["study/roadmap.md", "study/integrations.md", review],
            instance_mode=True,
        )
        assert any("study/integrations.md" in error for error in result.errors)


def test_reviewed_deletion_uses_base_fingerprint() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "review@example.com"],
            cwd=root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Review Test"],
            cwd=root,
            check=True,
        )
        write(
            root / ".open-study-path/instance.yml",
            "kind: open-study-path-instance\n",
        )
        write(root / "study/obsolete.md", "# Old content\n")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "base"], cwd=root, check=True
        )
        base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        previous = sha256(
            (root / "study/obsolete.md").read_bytes()
        ).hexdigest()
        (root / "study/obsolete.md").unlink()

        profile = REVIEW_PROFILES["migration"]
        review = "state/reviews/migration.yml"
        document = {
            "contract_version": 1,
            "operation_id": "migration-delete-v1",
            "phase": "migration",
            "reviewer_role": profile["reviewer_role"],
            "independent_pass": True,
            "status": "approved",
            "reviewed_at": "2026-07-30T12:00:00Z",
            "artifacts": [
                {
                    "path": "study/obsolete.md",
                    "change": "deleted",
                    "previous_sha256": previous,
                }
            ],
            "checks": {
                check: "passed" for check in profile["checks"]
            },
            "blocking_findings": [],
            "non_blocking_findings": [],
        }
        write(root / review, yaml.safe_dump(document, sort_keys=False))
        result = validate_changed_coverage(
            root,
            ["study/obsolete.md", review],
            instance_mode=True,
            base_sha=base_sha,
        )
        assert not result.errors, result.errors


def test_wrong_profile_cannot_cover_generated_artifact() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(
            root / ".open-study-path/instance.yml",
            "kind: open-study-path-instance\n",
        )
        write(root / "study/modules/TOPIC-001.md", "# Lesson\n")
        review = approved_review(
            root,
            phase="setup",
            artifacts=["study/modules/TOPIC-001.md"],
        )
        result = validate_changed_coverage(
            root,
            ["study/modules/TOPIC-001.md", review],
            instance_mode=True,
        )
        assert any(
            "out-of-scope artifact" in error for error in result.errors
        )


def test_review_path_cannot_escape_repository() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        review = "state/reviews/migration.yml"
        write(
            root / review,
            yaml.safe_dump(
                {
                    "phase": "migration",
                    "artifacts": [
                        {
                            "path": "study/../../outside.txt",
                            "sha256": "0" * 64,
                        }
                    ],
                },
                sort_keys=False,
            ),
        )
        errors = review_path_errors(root, [review])
        assert any("safe repository-relative path" in error for error in errors)


def test_review_cannot_fingerprint_symbolic_link() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "outside.txt", "outside\n")
        link = root / "study/link.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(root / "outside.txt")
        review = "state/reviews/curriculum.yml"
        write(
            root / review,
            yaml.safe_dump(
                {
                    "phase": "curriculum",
                    "artifacts": [
                        {"path": "study/link.md", "sha256": "0" * 64}
                    ],
                },
                sort_keys=False,
            ),
        )
        errors = review_path_errors(root, [review])
        assert any("symbolic link" in error for error in errors)


def test_enabled_framework_cannot_be_disabled() -> None:
    errors = instance_transition_errors(
        base_document={"review_framework": {"enabled": True}},
        head_document={"review_framework": {"enabled": False}},
        head_marker_exists=True,
        changed_review_phases=["migration"],
    )
    assert any("cannot be disabled" in error for error in errors)


def test_marker_deletion_requires_migration_review() -> None:
    blocked = instance_transition_errors(
        base_document={"review_framework": {"enabled": True}},
        head_document=None,
        head_marker_exists=False,
        changed_review_phases=["setup"],
    )
    assert any(
        "requires a changed approved migration review" in error
        for error in blocked
    )

    allowed = instance_transition_errors(
        base_document={"review_framework": {"enabled": True}},
        head_document=None,
        head_marker_exists=False,
        changed_review_phases=["migration"],
    )
    assert not allowed


def test_template_changes_do_not_require_instance_review() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "templates/topic.md", "# Template\n")
        result = validate_changed_coverage(
            root, ["templates/topic.md"], instance_mode=False
        )
        assert not result.errors


def test_generated_path_classifier() -> None:
    assert is_generated_artifact("study/roadmap.md")
    assert is_generated_artifact("state/progress.json")
    assert is_generated_artifact(".open-study-path/instance.yml")
    assert is_generated_artifact(
        ".github/ISSUE_TEMPLATE/assessment-topic-001.yml"
    )
    assert is_generated_artifact("README.md")
    assert not is_generated_artifact("state/reviews/intake.yml")
    assert not is_generated_artifact(
        "state/content-reviews/TOPIC-001.yml"
    )
    assert not is_generated_artifact("scripts/validate_template.py")


def test_usage_ledger_is_not_a_generated_artifact() -> None:
    # Etapa 6a: the shared per-dispatch cost/token ledger every phase's
    # workflow appends to is not something any review profile's checks
    # judge -- requiring it in `artifacts:` produced a real CI failure for
    # track and, unnoticed until this etapa, the same gap in the
    # already-merged diagnostic review.
    assert not is_generated_artifact("state/agent-pilot-usage.jsonl")
    # Still a normal state/ path for anything else with that shape.
    assert is_generated_artifact("state/agent-pilot-usage-summary.json")


def test_operation_journal_uses_dedicated_validation() -> None:
    assert uses_dedicated_validation(
        "state/operations/publication-trello-v1.json"
    )
    assert uses_dedicated_validation("state/content-reviews/TOPIC-001.yml")
    assert not uses_dedicated_validation("state/integrations.json")
    assert not uses_dedicated_validation("state/operations/readme.md")


def main() -> None:
    tests = [
        test_valid_intake_review,
        test_missing_review_blocks_generated_change,
        test_stale_hash_blocks_review,
        test_blocking_finding_prevents_approval,
        test_required_check_cannot_be_skipped,
        test_review_must_cover_every_generated_change,
        test_reviewed_deletion_uses_base_fingerprint,
        test_wrong_profile_cannot_cover_generated_artifact,
        test_review_path_cannot_escape_repository,
        test_review_cannot_fingerprint_symbolic_link,
        test_enabled_framework_cannot_be_disabled,
        test_marker_deletion_requires_migration_review,
        test_template_changes_do_not_require_instance_review,
        test_generated_path_classifier,
        test_usage_ledger_is_not_a_generated_artifact,
        test_operation_journal_uses_dedicated_validation,
    ]
    for test in tests:
        test()
    print(
        f"Review framework regression tests passed ({len(tests)} cases)."
    )


if __name__ == "__main__":
    main()
