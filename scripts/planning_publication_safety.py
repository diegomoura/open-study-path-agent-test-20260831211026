#!/usr/bin/env python3
"""Shared checks for topic-first planning and resumable external publication."""

from __future__ import annotations

import re
from typing import Any, Mapping

CALENDAR_PROJECTION_MARKER = (
    "<!-- open-study-path:calendar-projection explicitly_requested=true -->"
)

WEEKLY_STRUCTURE_PATTERNS = (
    re.compile(r"^#{1,6}\s+.*\b(semanal|semana|weekly|week)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\|\s*(semana|week)\s*\|", re.IGNORECASE | re.MULTILINE),
    re.compile(r"dura[cç][aã]o\s+projetada[^\n]*\bseman", re.IGNORECASE),
    re.compile(r"projected\s+duration[^\n]*\bweeks?\b", re.IGNORECASE),
    re.compile(r"^\|\s*\d+\s*\|[^\n]*\bTOPIC-\d+", re.IGNORECASE | re.MULTILINE),
)

DISPOSABLE_RESOURCE_NAMES = re.compile(
    r"^(tmp\d*|temp\d*|test\d*|probe\d*)$", re.IGNORECASE
)


def topic_first_violations(config: Mapping[str, Any], roadmap: str) -> list[str]:
    """Return roadmap violations when topics are the configured planning unit."""

    planning = config.get("planning", {})
    if not isinstance(planning, Mapping) or planning.get("unit") != "topic":
        return []
    if CALENDAR_PROJECTION_MARKER in roadmap:
        return []

    violations: list[str] = []
    for pattern in WEEKLY_STRUCTURE_PATTERNS:
        if pattern.search(roadmap):
            violations.append(pattern.pattern)
    return violations


def publication_state_violations(
    config: Mapping[str, Any], integrations: Mapping[str, Any]
) -> list[str]:
    """Check that a known task board and partial publication are durably journaled."""

    violations: list[str] = []
    integration_config = config.get("integrations", {})
    task_manager = (
        integration_config.get("task_manager", {})
        if isinstance(integration_config, Mapping)
        else {}
    )
    board = task_manager.get("board_or_project") if isinstance(task_manager, Mapping) else None

    resources = integrations.get("resources", [])
    if not isinstance(resources, list):
        resources = []

    if board:
        matched = any(
            isinstance(resource, Mapping)
            and resource.get("provider") == "trello"
            and board in {resource.get("url"), resource.get("external_id")}
            for resource in resources
        )
        if not matched:
            violations.append("configured Trello board is missing from integration resources")

    sync = integrations.get("sync", {})
    if isinstance(sync, Mapping) and sync.get("status") in {"partial", "in_progress"}:
        if not sync.get("last_attempt_at"):
            violations.append("partial publication must record last_attempt_at")
        if not resources:
            violations.append("partial publication must retain created resources")

    for resource in resources:
        if not isinstance(resource, Mapping):
            continue
        name = str(resource.get("name", "")).strip()
        if name and DISPOSABLE_RESOURCE_NAMES.fullmatch(name):
            violations.append(f"disposable external resource recorded: {name}")

    return violations
