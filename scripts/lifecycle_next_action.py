#!/usr/bin/env python3
"""Resolve the next learner-facing lifecycle command from persisted state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

PROPOSE_COMMAND = (
    "Gere uma proposta de trilha com base no intake e no diagnóstico. "
    "Abra um pull request e não publique tarefas ainda."
)
GENERATE_COMMAND = "Crie minha trilha de estudos."
PUBLISH_COMMAND = "Organize minha trilha nas ferramentas que escolhemos."
RESUME_PUBLISH_COMMAND = "Continue a organização da minha trilha nas ferramentas que escolhemos."
EVALUATE_COMMAND_TEMPLATE = "Terminei {lesson_title}. Avalie minhas respostas."
PUBLISHED_SYNC_STATUSES = {"success", "succeeded", "completed"}
PARTIAL_SYNC_STATUSES = {"partial", "in_progress", "action_required"}


@dataclass(frozen=True)
class NextAction:
    phase: str
    command: str
    reason: str


def _status(document: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(document, Mapping):
        return {}
    value = document.get("status", {})
    return value if isinstance(value, Mapping) else {}


def _sync(integrations: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(integrations, Mapping):
        return {}
    value = integrations.get("sync", {})
    return value if isinstance(value, Mapping) else {}


def integration_resolution_complete(integrations: Mapping[str, Any] | None) -> bool:
    if not isinstance(integrations, Mapping):
        return False
    selected = integrations.get("selected_capabilities", {})
    resolution = integrations.get("resolution")
    if isinstance(resolution, Mapping):
        status = str(resolution.get("status", "")).strip().lower()
        unresolved = resolution.get("unresolved_capabilities", [])
        return status == "resolved" and isinstance(unresolved, list) and not unresolved
    return not isinstance(selected, Mapping) or not selected


def publication_complete(integrations: Mapping[str, Any] | None) -> bool:
    sync = _sync(integrations)
    status = str(sync.get("status", "")).strip().lower()
    return (
        status in PUBLISHED_SYNC_STATUSES
        and bool(sync.get("last_success_at"))
        and integration_resolution_complete(integrations)
    )


def publication_has_progress(integrations: Mapping[str, Any] | None) -> bool:
    if not isinstance(integrations, Mapping):
        return False
    sync_status = str(_sync(integrations).get("status", "")).strip().lower()
    resolution = integrations.get("resolution", {})
    resolution_status = (
        str(resolution.get("status", "")).strip().lower()
        if isinstance(resolution, Mapping)
        else ""
    )
    resources = integrations.get("resources", [])
    has_resources = isinstance(resources, list) and bool(resources)
    return has_resources and (
        sync_status in PARTIAL_SYNC_STATUSES
        or resolution_status == "action_required"
        or not integration_resolution_complete(integrations)
    )


def resolve_next_action(
    instance: Mapping[str, Any] | None,
    integrations: Mapping[str, Any] | None,
    *,
    lesson_title: str = "<título da aula>",
) -> NextAction:
    """Return the only normal next phase and command allowed by persisted state."""

    status = _status(instance)

    if status.get("diagnostic_complete") is True and status.get("curriculum_proposed") is not True:
        return NextAction(
            phase="generate",
            command=PROPOSE_COMMAND,
            reason="curriculum_not_proposed",
        )

    if status.get("curriculum_generated") is not True:
        return NextAction(
            phase="generate",
            command=GENERATE_COMMAND,
            reason="curriculum_not_generated",
        )

    if publication_has_progress(integrations):
        return NextAction(
            phase="publish",
            command=RESUME_PUBLISH_COMMAND,
            reason="publication_partial_or_integration_action_required",
        )

    if not publication_complete(integrations):
        return NextAction(
            phase="publish",
            command=PUBLISH_COMMAND,
            reason="publication_pending",
        )

    title = lesson_title.strip() or "<título da aula>"
    return NextAction(
        phase="evaluate",
        command=EVALUATE_COMMAND_TEMPLATE.format(lesson_title=title),
        reason="publication_complete",
    )
