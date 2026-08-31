#!/usr/bin/env python3
"""Behavioral regressions for generation completion and stale-response prevention."""

from __future__ import annotations

from generation_terminal_state import resolve_generation_terminal_state


HEAD = "abc123"


def pull_request(*, merged: bool = False, draft: bool = True, state: str = "open", head: str = HEAD, mergeable: bool = True) -> dict:
    return {
        "head_sha": head,
        "state": state,
        "draft": draft,
        "merged": merged,
        "mergeable": mergeable,
        "merge_commit_sha": "merge456" if merged else None,
    }


def test_editorial_failure_requires_internal_correction() -> None:
    decision = resolve_generation_terminal_state(
        pull_request(),
        ["success", "failure"],
        HEAD,
    )
    assert decision.action == "correct_and_revalidate"
    assert decision.learner_success_allowed is False


def test_pending_checks_require_reread_not_success() -> None:
    decision = resolve_generation_terminal_state(
        pull_request(),
        ["success", "in_progress"],
        HEAD,
    )
    assert decision.action == "wait_and_reread"
    assert decision.learner_success_allowed is False


def test_green_draft_requires_merge() -> None:
    decision = resolve_generation_terminal_state(
        pull_request(draft=True),
        ["success", "success"],
        HEAD,
    )
    assert decision.action == "merge_current_head"
    assert decision.learner_success_allowed is False


def test_green_ready_pr_requires_merge() -> None:
    decision = resolve_generation_terminal_state(
        pull_request(draft=False),
        ["success", "success"],
        HEAD,
    )
    assert decision.action == "merge_current_head"
    assert decision.learner_success_allowed is False


def test_exact_merged_head_allows_success() -> None:
    decision = resolve_generation_terminal_state(
        pull_request(merged=True, draft=False, state="closed"),
        ["success", "success"],
        HEAD,
    )
    assert decision.action == "success"
    assert decision.learner_success_allowed is True


def test_stale_head_requires_fresh_readback() -> None:
    decision = resolve_generation_terminal_state(
        pull_request(head="new-head"),
        ["success", "success"],
        HEAD,
    )
    assert decision.action == "refresh_current_state"
    assert decision.learner_success_allowed is False


def test_material_decision_is_the_only_normal_owner_gate() -> None:
    decision = resolve_generation_terminal_state(
        pull_request(),
        ["success", "success"],
        HEAD,
        material_decision_required=True,
    )
    assert decision.action == "owner_action_required"
    assert decision.learner_success_allowed is False


def test_unavailable_verification_is_technical_not_editorial_blocker() -> None:
    decision = resolve_generation_terminal_state(
        pull_request(),
        ["success", "success"],
        HEAD,
        verification_unavailable=True,
    )
    assert decision.action == "technical_blocked"
    assert decision.learner_success_allowed is False


def test_closed_unmerged_pr_cannot_report_success() -> None:
    decision = resolve_generation_terminal_state(
        pull_request(merged=False, draft=False, state="closed"),
        ["success", "success"],
        HEAD,
    )
    assert decision.action == "technical_blocked"
    assert decision.learner_success_allowed is False


def main() -> None:
    test_editorial_failure_requires_internal_correction()
    test_pending_checks_require_reread_not_success()
    test_green_draft_requires_merge()
    test_green_ready_pr_requires_merge()
    test_exact_merged_head_allows_success()
    test_stale_head_requires_fresh_readback()
    test_material_decision_is_the_only_normal_owner_gate()
    test_unavailable_verification_is_technical_not_editorial_blocker()
    test_closed_unmerged_pr_cannot_report_success()
    print("Generation terminal-state regressions passed.")


if __name__ == "__main__":
    main()
