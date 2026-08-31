#!/usr/bin/env python3
"""Resolve whether a generation operation may finish, must continue, or is truly blocked."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sys
from typing import Any, Iterable, Mapping

SUCCESS = {"success", "succeeded", "passed", "completed"}
FAILURE = {"failure", "failed", "cancelled", "canceled", "timed_out", "action_required"}
PENDING = {"queued", "pending", "in_progress", "waiting", "requested"}


@dataclass(frozen=True)
class TerminalDecision:
    action: str
    reason: str
    learner_success_allowed: bool = False


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def _head_sha(pr: Mapping[str, Any]) -> str:
    direct = pr.get("head_sha")
    if direct:
        return str(direct).strip()
    head = pr.get("head")
    if isinstance(head, Mapping):
        return str(head.get("sha") or "").strip()
    return ""


def _check_state(check: Any) -> str:
    if isinstance(check, str):
        return _text(check)
    if not isinstance(check, Mapping):
        return "unknown"
    conclusion = _text(check.get("conclusion") or check.get("state"))
    status = _text(check.get("status"))
    if conclusion:
        return conclusion
    if status:
        return status
    return "unknown"


def resolve_generation_terminal_state(
    pr: Mapping[str, Any],
    checks: Iterable[Any],
    expected_head_sha: str,
    *,
    unresolved_review_threads: bool = False,
    material_decision_required: bool = False,
    verification_unavailable: bool = False,
) -> TerminalDecision:
    """Return the only safe next action for the current generation head.

    Editorial, schema, locator, fingerprint and review-coverage failures are internal
    correction work. They are never learner decisions. A successful learner-facing
    response is allowed only after a final read-back proves that the exact expected
    head passed its required checks and was merged.
    """

    expected = str(expected_head_sha or "").strip()
    current = _head_sha(pr)
    if not expected or not current or current != expected:
        return TerminalDecision(
            "refresh_current_state",
            "pull-request head changed or the expected head is missing",
        )

    if material_decision_required:
        return TerminalDecision(
            "owner_action_required",
            "a concrete learner decision changes scope, prerequisites, effort, or outcome",
        )

    if verification_unavailable:
        return TerminalDecision(
            "technical_blocked",
            "required current-head verification is unavailable",
        )

    states = [_check_state(check) for check in checks]
    if not states or any(state == "unknown" for state in states):
        return TerminalDecision(
            "refresh_current_state",
            "required checks are missing or unreadable for the current head",
        )

    if any(state in PENDING for state in states):
        return TerminalDecision(
            "wait_and_reread",
            "required checks are still running for the current head",
        )

    if any(state in FAILURE for state in states):
        return TerminalDecision(
            "correct_and_revalidate",
            "a required check failed and the operation must continue internally",
        )

    if unresolved_review_threads:
        return TerminalDecision(
            "correct_and_revalidate",
            "review threads remain unresolved",
        )

    if not all(state in SUCCESS for state in states):
        return TerminalDecision(
            "refresh_current_state",
            "check state is not recognized as terminal success",
        )

    merged = pr.get("merged") is True
    state = _text(pr.get("state"))
    draft = pr.get("draft") is True
    mergeable = pr.get("mergeable")

    if merged:
        if not pr.get("merge_commit_sha"):
            return TerminalDecision(
                "refresh_current_state",
                "merged pull request is missing merge confirmation",
            )
        return TerminalDecision(
            "success",
            "the exact current head passed required checks and is merged",
            learner_success_allowed=True,
        )

    if state == "closed":
        return TerminalDecision(
            "technical_blocked",
            "the pull request was closed without merging",
        )

    if state != "open":
        return TerminalDecision(
            "refresh_current_state",
            "pull-request state is not current",
        )

    if draft or mergeable is not True:
        return TerminalDecision(
            "merge_current_head",
            "checks passed but the pull request still requires readiness or mergeability handling",
        )

    return TerminalDecision(
        "merge_current_head",
        "checks passed and the exact current head must be merged before responding",
    )


def main() -> None:
    payload = json.load(sys.stdin)
    decision = resolve_generation_terminal_state(
        payload.get("pull_request", {}),
        payload.get("checks", []),
        payload.get("expected_head_sha", ""),
        unresolved_review_threads=bool(payload.get("unresolved_review_threads")),
        material_decision_required=bool(payload.get("material_decision_required")),
        verification_unavailable=bool(payload.get("verification_unavailable")),
    )
    print(json.dumps(asdict(decision), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
