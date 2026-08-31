#!/usr/bin/env python3
"""Behavioral regression tests for safe pull-request completion."""

from ci_completion_state import (
    Action,
    CheckObservation,
    CompletionContext,
    bounded_backoff_seconds,
    decide_next_action,
    discover_required_checks,
    estimate_wait_budget_seconds,
)


HEAD = "a" * 40
NEW_HEAD = "b" * 40
BASELINE = ("Validate Open Study Path", "Validate curriculum state")


def check(name: str, status: str, conclusion: str | None = None, head: str = HEAD):
    return CheckObservation(name=name, head_sha=head, status=status, conclusion=conclusion)


def context(**overrides) -> CompletionContext:
    values = {
        "expected_head_sha": HEAD,
        "current_head_sha": HEAD,
        "draft": False,
        "auto_merge_supported": False,
        "auto_merge_enabled": False,
        "merged": False,
        "default_branch_verified": False,
        "mergeable": True,
        "required_checks": BASELINE,
        "checks": tuple(check(name, "completed", "success") for name in BASELINE),
    }
    values.update(overrides)
    return CompletionContext(**values)


def assert_action(expected: Action, **overrides):
    decision = decide_next_action(context(**overrides))
    assert decision.action == expected, decision
    return decision


def main() -> None:
    # A reviewed draft must become ready before auto-merge is attempted.
    assert_action(Action.MARK_READY, draft=True, auto_merge_supported=True)
    assert_action(Action.ENABLE_AUTO_MERGE, auto_merge_supported=True)

    # Repositories without auto-merge use bounded polling and atomic manual merge.
    pending = tuple(check(name, "in_progress") for name in BASELINE)
    waiting = assert_action(Action.WAIT, checks=pending)
    assert waiting.wait_seconds == 10
    merge = assert_action(Action.MERGE_EXPECTED_HEAD)
    assert merge.expected_head_sha == HEAD

    # Any head movement invalidates all earlier observations.
    restart = assert_action(Action.RESTART_FOR_NEW_HEAD, current_head_sha=NEW_HEAD)
    assert restart.expected_head_sha == NEW_HEAD

    # Deterministic failures are repaired on the same branch; opaque failures block.
    failure = (
        check(BASELINE[0], "completed", "failure"),
        check(BASELINE[1], "completed", "success"),
    )
    assert_action(
        Action.REPAIR_DETERMINISTIC_FAILURE,
        checks=failure,
        deterministic_repair_available=True,
    )
    assert_action(Action.BLOCK_CHECK_FAILURE, checks=failure)

    # Cancelled or timed-out checks receive one retry only.
    cancelled = (
        check(BASELINE[0], "completed", "cancelled"),
        check(BASELINE[1], "completed", "success"),
    )
    assert_action(Action.RETRY_TRANSIENT, checks=cancelled)
    assert_action(Action.BLOCK_INFRASTRUCTURE, checks=cancelled, transient_retry_count=1)

    # Missing checks can never be treated as green.
    assert_action(
        Action.BLOCK_MISSING_CHECK,
        checks=(check(BASELINE[0], "completed", "success"),),
    )

    # A new concurrency run on another head does not satisfy the validated head.
    wrong_head = tuple(
        check(name, "completed", "success", head=NEW_HEAD) for name in BASELINE
    )
    assert_action(Action.BLOCK_MISSING_CHECK, checks=wrong_head)

    # An explicit no-merge request and a material decision are hard gates.
    assert_action(Action.BLOCK_NO_MERGE, no_merge_requested=True)
    assert_action(Action.BLOCK_MATERIAL_DECISION, unresolved_material_decision=True)

    # Merge conflicts remain visible instead of being bypassed.
    assert_action(Action.BLOCK_MERGE_CONFLICT, mergeable=False)

    # A merge is not complete until persisted state is read from the default branch.
    assert_action(Action.VERIFY_DEFAULT_BRANCH, merged=True)
    assert_action(Action.COMPLETE, merged=True, default_branch_verified=True)

    # Required checks are the deterministic union of branch protection and manifest.
    discovered = discover_required_checks(
        ["Validate Open Study Path"],
        [["Validate curriculum state"], ["Validate proposal completion"]],
    )
    assert discovered == (
        "Validate Open Study Path",
        "Validate curriculum state",
        "Validate proposal completion",
    )

    # Timing is calculated in memory, bounded and based on only five recent samples.
    estimate = estimate_wait_budget_seconds([50, 60, 70, 80, 90, 100])
    assert estimate.sample_count == 5
    assert estimate.median_seconds == 80
    assert estimate.p90_seconds == 100
    assert estimate.observation_budget_seconds == 180
    assert estimate_wait_budget_seconds([]).observation_budget_seconds == 600
    assert estimate_wait_budget_seconds([1000] * 5).observation_budget_seconds == 900

    assert [bounded_backoff_seconds(i) for i in range(7)] == [10, 15, 20, 30, 45, 45, 45]

    print("CI completion state-machine regression passed.")


if __name__ == "__main__":
    main()
