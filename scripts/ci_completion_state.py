#!/usr/bin/env python3
"""Pure state machine for safe pull-request completion.

This module does not call GitHub or sleep. It turns an observed repository state
into one explicit next action. Callers remain responsible for executing that
action and then rebuilding the context from fresh GitHub data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import median
from typing import Iterable, Sequence


class Action(str, Enum):
    BLOCK_NO_MERGE = "block_no_merge"
    BLOCK_MATERIAL_DECISION = "block_material_decision"
    RESTART_FOR_NEW_HEAD = "restart_for_new_head"
    MARK_READY = "mark_ready"
    ENABLE_AUTO_MERGE = "enable_auto_merge"
    WAIT = "wait"
    RETRY_TRANSIENT = "retry_transient"
    REPAIR_DETERMINISTIC_FAILURE = "repair_deterministic_failure"
    BLOCK_CHECK_FAILURE = "block_check_failure"
    BLOCK_MISSING_CHECK = "block_missing_check"
    BLOCK_INFRASTRUCTURE = "block_infrastructure"
    BLOCK_MERGE_CONFLICT = "block_merge_conflict"
    MERGE_EXPECTED_HEAD = "merge_expected_head"
    VERIFY_DEFAULT_BRANCH = "verify_default_branch"
    COMPLETE = "complete"


@dataclass(frozen=True)
class CheckObservation:
    name: str
    head_sha: str
    status: str
    conclusion: str | None = None


@dataclass(frozen=True)
class TimingEstimate:
    sample_count: int
    median_seconds: int
    p90_seconds: int
    observation_budget_seconds: int


@dataclass(frozen=True)
class CompletionContext:
    expected_head_sha: str
    current_head_sha: str
    draft: bool
    auto_merge_supported: bool
    auto_merge_enabled: bool
    merged: bool
    default_branch_verified: bool
    mergeable: bool | None
    required_checks: tuple[str, ...]
    checks: tuple[CheckObservation, ...]
    no_merge_requested: bool = False
    unresolved_material_decision: bool = False
    deterministic_repair_available: bool = False
    transient_retry_count: int = 0
    observation_budget_exhausted: bool = False


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str
    expected_head_sha: str | None = None
    wait_seconds: int | None = None


def discover_required_checks(
    branch_protection_checks: Iterable[str],
    operation_check_sets: Iterable[Iterable[str]],
) -> tuple[str, ...]:
    """Return the deterministic union of repository and operation requirements."""

    checks = {name.strip() for name in branch_protection_checks if name.strip()}
    for check_set in operation_check_sets:
        checks.update(name.strip() for name in check_set if name.strip())
    return tuple(sorted(checks))


def _nearest_rank_percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("at least one timing sample is required")
    rank = max(1, int((percentile * len(ordered)) + 0.999999))
    return ordered[min(rank - 1, len(ordered) - 1)]


def estimate_wait_budget_seconds(
    successful_duration_seconds: Sequence[float],
    *,
    default_seconds: int = 600,
    minimum_seconds: int = 180,
    maximum_seconds: int = 900,
) -> TimingEstimate:
    """Estimate a bounded wait budget in memory from up to five recent runs."""

    samples = [float(value) for value in successful_duration_seconds if value > 0][-5:]
    if not samples:
        budget = min(max(default_seconds, minimum_seconds), maximum_seconds)
        return TimingEstimate(0, 0, 0, budget)

    median_seconds = int(round(median(samples)))
    p90_seconds = int(round(_nearest_rank_percentile(samples, 0.90)))
    budget = int(round(max(median_seconds * 2, p90_seconds * 1.25)))
    budget = min(max(budget, minimum_seconds), maximum_seconds)
    return TimingEstimate(len(samples), median_seconds, p90_seconds, budget)


def bounded_backoff_seconds(attempt: int) -> int:
    schedule = (10, 15, 20, 30, 45)
    return schedule[min(max(attempt, 0), len(schedule) - 1)]


def _latest_checks_for_head(
    observations: Sequence[CheckObservation], expected_head_sha: str
) -> dict[str, CheckObservation]:
    latest: dict[str, CheckObservation] = {}
    for observation in observations:
        if observation.head_sha == expected_head_sha:
            latest[observation.name] = observation
    return latest


def decide_next_action(context: CompletionContext, *, attempt: int = 0) -> Decision:
    """Return exactly one safe action for the current fresh repository snapshot."""

    if context.no_merge_requested:
        return Decision(Action.BLOCK_NO_MERGE, "the learner explicitly requested no merge")

    if context.unresolved_material_decision:
        return Decision(
            Action.BLOCK_MATERIAL_DECISION,
            "a material learner decision is still unresolved",
        )

    if context.current_head_sha != context.expected_head_sha:
        return Decision(
            Action.RESTART_FOR_NEW_HEAD,
            "the pull-request head changed after validation began",
            expected_head_sha=context.current_head_sha,
        )

    if context.draft:
        return Decision(
            Action.MARK_READY,
            "review is complete; a draft cannot be auto-merged or merged",
            expected_head_sha=context.expected_head_sha,
        )

    if context.mergeable is False:
        return Decision(
            Action.BLOCK_MERGE_CONFLICT,
            "the validated head is not mergeable",
            expected_head_sha=context.expected_head_sha,
        )

    if context.merged:
        if context.default_branch_verified:
            return Decision(
                Action.COMPLETE,
                "the merged state was confirmed on the default branch",
                expected_head_sha=context.expected_head_sha,
            )
        return Decision(
            Action.VERIFY_DEFAULT_BRANCH,
            "the pull request merged but persisted lifecycle state is not verified yet",
            expected_head_sha=context.expected_head_sha,
        )

    if context.auto_merge_supported and not context.auto_merge_enabled:
        return Decision(
            Action.ENABLE_AUTO_MERGE,
            "the pull request is ready; auto-merge is the preferred completion path",
            expected_head_sha=context.expected_head_sha,
        )

    observed = _latest_checks_for_head(context.checks, context.expected_head_sha)
    missing = [name for name in context.required_checks if name not in observed]
    if missing:
        return Decision(
            Action.BLOCK_MISSING_CHECK,
            "required checks are missing for the exact validated head: " + ", ".join(missing),
            expected_head_sha=context.expected_head_sha,
        )

    pending = []
    failed = []
    transient = []
    for name in context.required_checks:
        check = observed[name]
        if check.status != "completed":
            pending.append(name)
            continue
        conclusion = check.conclusion or ""
        if conclusion == "success":
            continue
        if conclusion in {"cancelled", "timed_out"}:
            transient.append(name)
        else:
            failed.append(name)

    if failed:
        if context.deterministic_repair_available:
            return Decision(
                Action.REPAIR_DETERMINISTIC_FAILURE,
                "a deterministic repair is available for: " + ", ".join(failed),
                expected_head_sha=context.expected_head_sha,
            )
        return Decision(
            Action.BLOCK_CHECK_FAILURE,
            "required checks failed without a safe deterministic repair: "
            + ", ".join(failed),
            expected_head_sha=context.expected_head_sha,
        )

    if transient:
        if context.transient_retry_count < 1:
            return Decision(
                Action.RETRY_TRANSIENT,
                "retry the transient check outcome once: " + ", ".join(transient),
                expected_head_sha=context.expected_head_sha,
            )
        return Decision(
            Action.BLOCK_INFRASTRUCTURE,
            "transient checks failed again after the single retry: "
            + ", ".join(transient),
            expected_head_sha=context.expected_head_sha,
        )

    if pending:
        if context.observation_budget_exhausted:
            return Decision(
                Action.BLOCK_INFRASTRUCTURE,
                "checks are still pending after the bounded observation budget: "
                + ", ".join(pending),
                expected_head_sha=context.expected_head_sha,
            )
        return Decision(
            Action.WAIT,
            "required checks are still running for the validated head",
            expected_head_sha=context.expected_head_sha,
            wait_seconds=bounded_backoff_seconds(attempt),
        )

    return Decision(
        Action.MERGE_EXPECTED_HEAD,
        "all required checks passed for the unchanged head",
        expected_head_sha=context.expected_head_sha,
    )
