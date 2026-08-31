#!/usr/bin/env python3
"""Deterministic branch/PR convergence rules for automated operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping

_OPERATION_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")


@dataclass(frozen=True)
class BranchPlan:
    operation_id: str
    branch: str
    pull_request: int | None
    commit_budget: int
    commits_before_open: int
    action: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def operation_branch_name(operation_id: str) -> str:
    if not _OPERATION_ID.fullmatch(operation_id):
        raise ValueError(f"invalid operation_id: {operation_id}")
    normalized = operation_id.replace(".", "-").replace("_", "-")
    return f"agent/operation-{normalized}"


def plan_branch_convergence(
    *,
    operation_id: str,
    journal: Mapping[str, Any] | None,
    observed_commit_count: int,
    existing_pull_request: int | None = None,
    commit_budget: int = 1,
) -> BranchPlan:
    """Return the single branch/PR action for a resumable operation.

    Intermediate local corrections never require another branch. If commits were
    created before validation, the deterministic action is to rebuild/squash the
    same branch before opening or updating the same PR.
    """
    if commit_budget < 1:
        raise ValueError("commit_budget must be positive")
    branch = operation_branch_name(operation_id)
    journal = dict(journal or {})
    journal_branch = journal.get("branch")
    if journal_branch and journal_branch != branch:
        raise ValueError("operation journal points to a different branch")
    journal_pr = journal.get("pull_request")
    if journal_pr and existing_pull_request and journal_pr != existing_pull_request:
        raise ValueError("operation journal points to a different pull request")
    pull_request = existing_pull_request or journal_pr

    if observed_commit_count > commit_budget:
        action = "rebuild_same_branch_single_commit"
    elif pull_request is None:
        action = "open_single_draft_pr_after_validation"
    else:
        action = "update_same_pr"

    return BranchPlan(
        operation_id=operation_id,
        branch=branch,
        pull_request=pull_request,
        commit_budget=commit_budget,
        commits_before_open=min(observed_commit_count, commit_budget),
        action=action,
    )
