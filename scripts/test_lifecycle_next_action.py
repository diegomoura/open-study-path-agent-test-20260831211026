#!/usr/bin/env python3
"""Behavioral regression tests for lifecycle next-action resolution."""

from __future__ import annotations

from lifecycle_next_action import (
    EVALUATE_COMMAND_TEMPLATE,
    GENERATE_COMMAND,
    PROPOSE_COMMAND,
    PUBLISH_COMMAND,
    RESUME_PUBLISH_COMMAND,
    integration_resolution_complete,
    publication_complete,
    resolve_next_action,
)


def instance(*, diagnostic: bool = True, proposed: bool = True, approved: bool = True, generated: bool) -> dict:
    return {
        "status": {
            "diagnostic_complete": diagnostic,
            "curriculum_proposed": proposed,
            "curriculum_approved": approved,
            "curriculum_generated": generated,
        }
    }


def integrations(
    status: str = "not_started",
    success_at: str | None = None,
    *,
    resources: list | None = None,
    selected: dict | None = None,
    resolution_status: str | None = None,
    unresolved: list[str] | None = None,
) -> dict:
    document = {
        "selected_capabilities": selected or {},
        "resources": resources or [],
        "sync": {
            "status": status,
            "last_success_at": success_at,
        },
    }
    if resolution_status is not None:
        document["resolution"] = {
            "status": resolution_status,
            "unresolved_capabilities": unresolved or [],
            "validated_at": "2026-07-29T23:00:00Z",
        }
    return document


def test_diagnostic_routes_to_automatic_proposal() -> None:
    action = resolve_next_action(
        instance(proposed=False, approved=False, generated=False),
        integrations(),
    )
    assert action.phase == "generate"
    assert action.command == PROPOSE_COMMAND
    assert "Abra um pull request" in action.command
    assert "não publique tarefas ainda" in action.command


def test_approved_proposal_routes_to_generation() -> None:
    action = resolve_next_action(instance(generated=False), integrations())
    assert action.phase == "generate"
    assert action.command == GENERATE_COMMAND


def test_agent_authored_deferral_cannot_skip_publication() -> None:
    action = resolve_next_action(instance(generated=True), integrations("not_started"))
    assert action.phase == "publish"
    assert action.command == PUBLISH_COMMAND
    assert "Avalie minhas respostas" not in action.command


def test_missing_integration_state_keeps_publication_pending() -> None:
    action = resolve_next_action(instance(generated=True), None)
    assert action.phase == "publish"
    assert action.command == PUBLISH_COMMAND


def test_failed_or_unrecorded_partial_publication_restarts_safely() -> None:
    for status in ["failed", "blocked", "partial", "in_progress"]:
        action = resolve_next_action(instance(generated=True), integrations(status))
        assert action.phase == "publish", status
        assert action.command == PUBLISH_COMMAND, status


def test_recorded_partial_publication_uses_resume_command() -> None:
    state = integrations(
        "partial",
        resources=[
            {
                "provider": "trello",
                "external_type": "board",
                "external_id": "1WDlmBlM",
            }
        ],
    )
    action = resolve_next_action(instance(generated=True), state)
    assert action.phase == "publish"
    assert action.reason == "publication_partial_or_integration_action_required"
    assert action.command == RESUME_PUBLISH_COMMAND
    assert "1WDlmBlM" not in action.command


def test_success_requires_timestamp() -> None:
    assert publication_complete(integrations("success", None)) is False
    action = resolve_next_action(instance(generated=True), integrations("success", None))
    assert action.phase == "publish"


def test_selected_capabilities_require_resolution_contract() -> None:
    state = integrations(
        "success",
        "2026-07-28T22:00:00Z",
        resources=[{"provider": "trello"}],
        selected={"task_manager": {"provider": "trello", "status": "success"}},
    )
    assert integration_resolution_complete(state) is False
    action = resolve_next_action(instance(generated=True), state)
    assert action.phase == "publish"
    assert action.command == RESUME_PUBLISH_COMMAND


def test_unresolved_email_or_quizlet_blocks_evaluation() -> None:
    state = integrations(
        "action_required",
        resources=[{"provider": "trello"}],
        selected={
            "task_manager": {
                "provider": "trello",
                "status": "success",
                "resolution_status": "resolved",
            },
            "formative_practice": {
                "provider": "markdown_flashcards",
                "status": "fallback_active",
                "resolution_status": "action_required",
            },
            "notifications": {
                "provider": "gmail",
                "status": "pending_configuration",
                "resolution_status": "action_required",
            },
        },
        resolution_status="action_required",
        unresolved=["formative_practice", "notifications"],
    )
    action = resolve_next_action(instance(generated=True), state)
    assert action.phase == "publish"
    assert action.command == RESUME_PUBLISH_COMMAND


def test_evaluation_is_available_only_after_publication_and_resolution() -> None:
    state = integrations(
        "success",
        "2026-07-28T22:00:00Z",
        resources=[{"provider": "trello"}],
        selected={
            "task_manager": {
                "provider": "trello",
                "status": "success",
                "resolution_status": "resolved",
            },
            "formative_practice": {
                "provider": "markdown_flashcards",
                "status": "fallback_active",
                "resolution_status": "resolved",
                "connection_offer_status": "shown",
            },
            "notifications": {
                "provider": "gmail",
                "status": "configured",
                "delivery_policy": "on_request",
                "resolution_status": "resolved",
            },
        },
        resolution_status="resolved",
    )
    action = resolve_next_action(
        instance(generated=True),
        state,
        lesson_title="Como os LLMs geram texto",
    )
    assert action.phase == "evaluate"
    assert action.command == EVALUATE_COMMAND_TEMPLATE.format(
        lesson_title="Como os LLMs geram texto"
    )


def main() -> None:
    test_diagnostic_routes_to_automatic_proposal()
    test_approved_proposal_routes_to_generation()
    test_agent_authored_deferral_cannot_skip_publication()
    test_missing_integration_state_keeps_publication_pending()
    test_failed_or_unrecorded_partial_publication_restarts_safely()
    test_recorded_partial_publication_uses_resume_command()
    test_success_requires_timestamp()
    test_selected_capabilities_require_resolution_contract()
    test_unresolved_email_or_quizlet_blocks_evaluation()
    test_evaluation_is_available_only_after_publication_and_resolution()
    print("Lifecycle next-action behavioral regressions passed.")


if __name__ == "__main__":
    main()
