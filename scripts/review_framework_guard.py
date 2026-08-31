#!/usr/bin/env python3
"""Security and lifecycle guards around generated-artifact review evidence."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml

from review_framework import is_review_path, normalize_path

INSTANCE_MARKER = ".open-study-path/instance.yml"


def _review_enabled(document: Any) -> bool:
    if not isinstance(document, dict):
        return False
    framework = document.get("review_framework")
    return isinstance(framework, dict) and framework.get("enabled") is True


def review_phases(root: Path, paths: Iterable[str]) -> tuple[str, ...]:
    phases: set[str] = set()
    for raw_path in paths:
        relative = normalize_path(raw_path)
        if not is_review_path(relative):
            continue
        target = root / relative
        if not target.is_file() or target.is_symlink():
            continue
        try:
            document = yaml.safe_load(target.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(document, dict):
            phase = str(document.get("phase") or "").strip()
            if phase:
                phases.add(phase)
    return tuple(sorted(phases))


def review_path_errors(root: Path, paths: Iterable[str]) -> tuple[str, ...]:
    errors: list[str] = []
    for raw_review_path in paths:
        review_path = normalize_path(raw_review_path)
        if not is_review_path(review_path):
            continue
        review_file = root / review_path
        if review_file.is_symlink():
            errors.append(f"review artifact cannot be a symbolic link: {review_path}")
            continue
        if not review_file.is_file():
            continue
        try:
            document = yaml.safe_load(review_file.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        artifacts = document.get("artifacts", []) if isinstance(document, dict) else []
        if not isinstance(artifacts, list):
            continue
        for index, entry in enumerate(artifacts):
            if not isinstance(entry, dict):
                continue
            raw_artifact = str(entry.get("path") or "")
            candidate = PurePosixPath(raw_artifact)
            if not raw_artifact or candidate.is_absolute() or ".." in candidate.parts:
                errors.append(
                    f"{review_path} artifact #{index + 1} must be a safe repository-relative path: "
                    f"{raw_artifact or '<missing>'}"
                )
                continue
            relative = normalize_path(raw_artifact)
            target = root / relative
            if target.is_symlink():
                errors.append(f"{review_path} cannot fingerprint a symbolic link: {relative}")
    return tuple(errors)


def instance_transition_errors(
    *,
    base_document: Any,
    head_document: Any,
    head_marker_exists: bool,
    changed_review_phases: Iterable[str],
) -> tuple[str, ...]:
    errors: list[str] = []
    base_enabled = _review_enabled(base_document)
    head_enabled = _review_enabled(head_document)

    if base_enabled and head_marker_exists and not head_enabled:
        errors.append("review_framework cannot be disabled after it has been enabled")

    if base_enabled and not head_marker_exists and "migration" not in set(changed_review_phases):
        errors.append(
            "deleting .open-study-path/instance.yml requires a changed approved migration review"
        )

    return tuple(errors)
