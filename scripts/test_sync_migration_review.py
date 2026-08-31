#!/usr/bin/env python3
"""Behavioral regressions for scripts/sync_migration_review.py."""

from __future__ import annotations

from pathlib import Path
import tempfile

import yaml

from review_framework import validate_review_document
from sync_migration_review import build_migration_review
from validate_instance_operation_scope import ROOT, migration_review_present


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_produced_document_passes_validate_review_document() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "README.md", "# Example instance\n")

        document = build_migration_review(
            root=root,
            operation_id="template-sync-example",
            notes=["Synced scripts/ and docs/ only; no instance state or study content touched."],
        )
        relative = "state/reviews/agent-pilot-template-sync.yml"
        write(root / relative, yaml.safe_dump(document, sort_keys=False))

        validation = validate_review_document(root, relative, base_sha=None)
        assert validation.errors == (), validation.errors
        assert validation.phase == "migration"


def test_migration_review_present_recognizes_the_produced_document() -> None:
    # validate_instance_operation_scope.migration_review_present hardcodes its
    # own ROOT (the real repository this test runs in) rather than accepting
    # one -- so exercising it for real means writing into a real, temporary
    # path under this repository's state/reviews/ (README.md always exists
    # here) and cleaning up after.
    document = build_migration_review(
        root=ROOT,
        operation_id="template-sync-example",
        notes=["Synced scripts/ and docs/ only."],
    )
    relative = "state/reviews/_test_sync_migration_review_scratch.yml"
    target_path = ROOT / relative
    try:
        write(target_path, yaml.safe_dump(document, sort_keys=False))
        assert migration_review_present([relative]) is True
        assert migration_review_present(["state/reviews/does-not-exist.yml"]) is False
    finally:
        target_path.unlink(missing_ok=True)


def test_rejects_an_artifact_path_review_framework_does_not_recognize() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "scripts/some_script.py", "print('hi')\n")
        try:
            build_migration_review(
                root=root,
                operation_id="bad",
                notes=["note"],
                attested_artifact="scripts/some_script.py",
            )
        except ValueError as exc:
            assert "not a generated artifact" in str(exc)
        else:
            raise SystemExit("expected ValueError for a non-generated-artifact path")


def test_rejects_a_missing_attested_artifact() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        try:
            build_migration_review(root=root, operation_id="bad", notes=["note"])
        except FileNotFoundError:
            pass
        else:
            raise SystemExit("expected FileNotFoundError for a missing attested artifact")


def test_rejects_empty_notes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write(root / "README.md", "# Example instance\n")
        try:
            build_migration_review(root=root, operation_id="bad", notes=[])
        except ValueError as exc:
            assert "notes must not be empty" in str(exc)
        else:
            raise SystemExit("expected ValueError for empty notes")


def main() -> None:
    test_produced_document_passes_validate_review_document()
    test_migration_review_present_recognizes_the_produced_document()
    test_rejects_an_artifact_path_review_framework_does_not_recognize()
    test_rejects_a_missing_attested_artifact()
    test_rejects_empty_notes()
    print("Template-sync migration review regressions passed.")


if __name__ == "__main__":
    main()
