#!/usr/bin/env python3
"""Resolve and validate integrations that are active for the learner now."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

VALID_RESOLUTION_STATUSES = {"resolved", "action_required"}
NONE_VALUES = {"", "none", "disabled", "false", "null"}
NO_EXTERNAL_ACCOUNTS = "no_external_accounts"

# Every key that scripts/task_projection_engine.py's normalized_integration_state()
# legitimately writes onto a state["resources"][*] entry, across every resource
# kind it builds (task_manager container, section/list, orientation, lesson,
# reminder). This is the enforcement side of instructions/50-track-progress.md's
# "Update state/integrations.json only with safe external identifiers, content
# versions, authority, synchronization status and timestamps" rule: that
# sentence alone did not stop `track`'s author from writing an ad hoc
# `activity_checkpoint` object into a resource entry, which run_publish_projection
# then silently discarded on the next republish (normalized_integration_state
# rebuilds `resources` from scratch and has no path for unknown per-resource
# keys). Keep this set in sync with normalized_integration_state() if that
# function's resource shapes change.
ALLOWED_RESOURCE_KEYS = {
    "capability",
    "provider",
    "type",
    "id",
    "url",
    "name",
    "position",
    "title",
    "topic_id",
    "visible_lesson_number",
    "direct_prerequisite_ids",
    "content_version",
    "canonical_state",
    "visible_state",
    "visual_position",
    "managed_fields_version",
    "roadmap_fingerprint",
    "target_url",
    "sync_status",
    "last_synced_at",
}


@dataclass(frozen=True)
class ResolutionResult:
    expected: tuple[str, ...]
    unresolved: tuple[str, ...]
    errors: tuple[str, ...]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def _no_external_accounts(config: Mapping[str, Any]) -> bool:
    preferences = _mapping(config.get("integration_preferences"))
    return _text(preferences.get("account_connections")) == NO_EXTERNAL_ACCOUNTS


def _publication_started(state: Mapping[str, Any]) -> bool:
    selected = _mapping(state.get("selected_capabilities"))
    resources = state.get("resources")
    resolution = _mapping(state.get("resolution"))
    sync = _mapping(state.get("sync"))
    return any(
        [
            bool(selected),
            bool(resources),
            _text(sync.get("status")) not in {"", "not_started"},
            bool(sync.get("last_attempt_at")),
            bool(sync.get("last_success_at")),
            _text(resolution.get("status")) not in {"", "not_started"},
            bool(resolution.get("validated_at")),
        ]
    )


def validate_account_policy(config: Mapping[str, Any], plan_markdown: str) -> list[str]:
    if not _no_external_accounts(config):
        return []

    errors: list[str] = []
    integrations = _mapping(config.get("integrations"))
    explicit_external = {
        "task_manager": (_mapping(integrations.get("task_manager")), "provider", {"trello", "todoist"}),
        "research": (_mapping(integrations.get("research")), "provider", {"consensus"}),
        "reminders": (_mapping(integrations.get("reminders")), "provider", {"todoist", "calendar"}),
        "calendar": (_mapping(integrations.get("calendar")), "provider", {"google_calendar", "outlook_calendar"}),
        "habit_tracking": (_mapping(integrations.get("habit_tracking")), "provider", {"habitify"}),
        "visual_workspace": (_mapping(integrations.get("visual_workspace")), "external_provider", {"whimsical", "miro", "lucid", "figma"}),
        "artifact_workspace": (_mapping(integrations.get("artifact_workspace")), "provider", {"google_drive", "notion", "sharepoint", "dropbox"}),
        "analytics_projection": (_mapping(integrations.get("analytics_projection")), "provider", {"airtable"}),
    }
    for capability, (section, key, providers) in explicit_external.items():
        provider = _text(section.get(key))
        if provider in providers:
            errors.append(
                f"{capability} selects external provider {provider} while account_connections is no_external_accounts"
            )

    notifications = _mapping(integrations.get("notifications"))
    if notifications.get("email_enabled") is True or _text(notifications.get("provider")) not in {"", "chat", "none"}:
        errors.append("notifications cannot use email while account_connections is no_external_accounts")

    lower = plan_markdown.lower()
    if plan_markdown and "account_connections: no_external_accounts" not in lower:
        errors.append("no-external-account integration plan must record account_connections: no_external_accounts")
    if "connection-offer eligibility: eligible" in lower or "connection_offer_status: shown" in lower:
        errors.append("no-external-account integration plan cannot make an app connection offer eligible")
    return errors


def expected_capabilities(config: Mapping[str, Any]) -> dict[str, str]:
    integrations = _mapping(config.get("integrations"))
    preferences = _mapping(config.get("integration_preferences"))
    routine = _mapping(preferences.get("routine"))
    expected: dict[str, str] = {}

    task = _mapping(integrations.get("task_manager"))
    task_provider = _text(task.get("provider"))
    if task_provider not in NONE_VALUES | {"auto"}:
        expected["task_manager"] = task_provider

    if _no_external_accounts(config):
        return expected

    routine_mode = _text(routine.get("mode"))
    calendar = _mapping(integrations.get("calendar"))
    reminders = _mapping(integrations.get("reminders"))

    if routine_mode == "fixed_calendar":
        provider = _text(calendar.get("provider"))
        if provider not in NONE_VALUES | {"auto"} and _text(calendar.get("enabled")) == "enabled":
            expected["scheduling"] = provider
    elif routine_mode == "flexible_reminders":
        provider = _text(reminders.get("provider"))
        if provider not in NONE_VALUES | {"auto"} and _text(reminders.get("enabled")) == "enabled":
            expected["reminders"] = provider
    elif routine_mode == "custom":
        calendar_provider = _text(calendar.get("provider"))
        reminder_provider = _text(reminders.get("provider"))
        if calendar_provider not in NONE_VALUES | {"auto"} and _text(calendar.get("enabled")) == "enabled":
            expected["scheduling"] = calendar_provider
        elif reminder_provider not in NONE_VALUES | {"auto"} and _text(reminders.get("enabled")) == "enabled":
            expected["reminders"] = reminder_provider

    return expected


def validate_plan(config: Mapping[str, Any], plan_markdown: str) -> list[str]:
    errors = validate_account_policy(config, plan_markdown)
    lower = plan_markdown.lower()
    routine = _mapping(_mapping(config.get("integration_preferences")).get("routine"))
    mode = _text(routine.get("mode"))

    if plan_markdown and mode and mode not in lower:
        errors.append(f"integration plan must record routine mode: {mode}")
    if "quizlet" in lower or "flashcard" in lower or ".tsv" in lower:
        errors.append("integration plan must not include removed flashcard capabilities")
    if "provider: gmail" in lower or "provider: outlook_email" in lower:
        errors.append("email must remain an on-request action, not a selected publication integration")
    return errors


def _capability_resolved(name: str, entry: Mapping[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    status = _text(entry.get("status"))
    resolution_status = _text(entry.get("resolution_status"))
    if resolution_status not in VALID_RESOLUTION_STATUSES:
        return False, [f"{name} has invalid resolution_status: {resolution_status or '<missing>'}"]

    if name == "task_manager":
        resolved = status in {"success", "completed"} and resolution_status == "resolved"
        if not resolved:
            errors.append("task_manager must be successful before publication resolves")
        return resolved, errors

    if name in {"scheduling", "reminders"}:
        if status in {"success", "completed", "declined", "unavailable"}:
            resolved = resolution_status == "resolved"
        elif status in {"pending_configuration", "action_required"}:
            resolved = False
        else:
            resolved = False
        if not resolved:
            errors.append(f"{name} requires complete routine details or an explicit terminal disposition")
        return resolved, errors

    resolved = resolution_status == "resolved"
    if not resolved:
        errors.append(f"{name} remains unresolved")
    return resolved, errors


def _validate_resource_shapes(state: Mapping[str, Any]) -> list[str]:
    """Reject any resources[] entry carrying keys outside ALLOWED_RESOURCE_KEYS.

    This is a deterministic guardrail for Achado 2 (activity_checkpoint
    silently discarded on republish): rather than trust an author to keep
    following the "only safe external identifiers, content versions,
    authority, synchronization status and timestamps" instruction, fail the
    review loudly the moment any ad hoc field lands in a resource entry --
    before it can be silently dropped later.
    """
    errors: list[str] = []
    resources = state.get("resources")
    if not isinstance(resources, list):
        return errors
    for index, resource in enumerate(resources):
        if not isinstance(resource, Mapping):
            continue
        extra = sorted(set(resource.keys()) - ALLOWED_RESOURCE_KEYS)
        if extra:
            errors.append(
                f"resources[{index}] has fields outside the managed schema: {extra}. "
                "Application/activity data belongs in state/progress.json, not "
                "state/integrations.json."
            )
    return errors


def validate_documents(
    config: Mapping[str, Any],
    state: Mapping[str, Any],
    plan_markdown: str,
) -> ResolutionResult:
    errors = validate_plan(config, plan_markdown) if plan_markdown else validate_account_policy(config, "")
    errors.extend(_validate_resource_shapes(state))
    expected = expected_capabilities(config)
    selected = _mapping(state.get("selected_capabilities"))
    resolution = _mapping(state.get("resolution"))
    resolution_status = _text(resolution.get("status"))
    declared_unresolved = tuple(sorted(_text(value) for value in resolution.get("unresolved_capabilities", []) if value))
    sync = _mapping(state.get("sync"))

    if not _publication_started(state):
        if resolution and resolution_status != "not_started":
            errors.append(f"pristine publication resolution.status must be not_started, got {resolution_status or '<missing>'}")
        if declared_unresolved:
            errors.append("pristine publication cannot declare unresolved capabilities")
        return ResolutionResult(tuple(sorted(expected)), (), tuple(errors))

    unresolved: list[str] = []
    if resolution_status == "not_started":
        errors.append("resolution.status cannot remain not_started after publication begins")

    for capability, provider in expected.items():
        entry = _mapping(selected.get(capability))
        if not entry:
            errors.append(f"selected capability disappeared from publication state: {capability}")
            unresolved.append(capability)
            continue
        state_provider = _text(entry.get("provider"))
        if state_provider and state_provider != provider:
            errors.append(f"{capability} provider changed from {provider} to {state_provider}")
        resolved, capability_errors = _capability_resolved(capability, entry)
        errors.extend(capability_errors)
        if not resolved:
            unresolved.append(capability)

    forbidden = {"formative_practice", "notifications"}.intersection(selected)
    for capability in sorted(forbidden):
        errors.append(f"removed or on-request capability must not be selected during publication: {capability}")

    computed_unresolved = tuple(sorted(set(unresolved)))
    if expected and not resolution:
        errors.append("publication state is missing top-level integration resolution")
    if resolution:
        expected_status = "resolved" if not computed_unresolved else "action_required"
        if resolution_status != expected_status:
            errors.append(f"resolution.status must be {expected_status}, got {resolution_status or '<missing>'}")
        if declared_unresolved != computed_unresolved:
            errors.append(
                "resolution.unresolved_capabilities does not match computed unresolved capabilities: "
                f"expected {computed_unresolved}, got {declared_unresolved}"
            )

    if _text(sync.get("status")) in {"success", "succeeded", "completed"} and computed_unresolved:
        errors.append("sync.status cannot be success while selected integrations remain unresolved")

    return ResolutionResult(tuple(sorted(expected)), computed_unresolved, tuple(errors))
