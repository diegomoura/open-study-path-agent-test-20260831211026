#!/usr/bin/env python3
"""Reverse a stuck ``intake:imported`` label left by an abandoned intake PR.

``label_github_issue`` (scripts/agent_runtime.py) is a live GitHub side
effect applied as part of a single author turn, before that turn's changes
land anywhere durable. If the turn's pull request is later closed without
merging -- for example because a real dispatch bug broke the diff and an
operator abandoned the PR rather than letting it self-repair in the same
PR (see instructions/11-intake-completion-recovery.md, which only covers
same-PR repair) -- the source issue is left permanently labeled
``intake:imported`` with no corresponding merged state. Every subsequent
``intake`` dispatch then treats that issue as already handled
(``scripts/intake_resolution.py``'s ``classify_issue`` excludes anything
carrying ``IMPORTED_LABEL``), silently excluding a submission that was
never actually imported.

This is a real, recurring operational trap: three real dispatches in the
same Etapa 12/14 validation session hit it, each requiring a manual
``DELETE /repos/{repo}/issues/{n}/labels/intake:imported`` call before the
next retry could see the issue as a candidate again.

``resolve_release_action`` is the pure decision function (network-free,
directly testable). ``release_stuck_intake_import`` is the thin CLI
wrapper that fetches the PR and the issue, decides, and -- only when every
safety check passes -- removes the label via the GitHub API. It never
touches an issue whose import is genuinely still current on the target
branch, and it never touches a PR that is open or was actually merged.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Callable, Sequence
from urllib.error import HTTPError
from urllib.request import Request, urlopen

IMPORTED_LABEL = "intake:imported"
SOURCE_REFERENCE_PATTERN = re.compile(r"^github_issue:(?P<repository>[^#]+)#(?P<number>\d+)$")

RequestJson = Callable[[str, str, dict[str, Any] | None], Any]


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"GitHub API error {status}: {message}")
        self.status = status


@dataclass(frozen=True)
class ReleaseDecision:
    should_release: bool
    issue_number: int | None
    reason: str


def parse_source_issue(source_reference: str | None, target_repo: str) -> int | None:
    """Return the issue number, or None if source_reference doesn't apply here.

    Mirrors scripts/agent_pilot_merge_digest.py's parse_source_issue_number:
    only trusts a reference whose repository matches target_repo exactly,
    and never raises on a missing or malformed value.
    """

    if not source_reference:
        return None
    match = SOURCE_REFERENCE_PATTERN.match(source_reference)
    if not match or match.group("repository") != target_repo:
        return None
    return int(match.group("number"))


def resolve_release_action(
    *,
    pr_state: str,
    pr_merged: bool,
    pr_head_ref: str,
    target_repo: str,
    pr_head_intake_summary_source_reference: str | None,
    main_intake_summary_source_reference: str | None,
    issue_labels: Sequence[str] = (),
) -> ReleaseDecision:
    """Decide whether to release the stuck label. Pure, network-free.

    ``pr_head_intake_summary_source_reference`` comes from
    state/intake-summary.json at the PR's head SHA (still fetchable via the
    GitHub API for a same-repo PR even after its branch has been deleted).
    ``main_intake_summary_source_reference`` comes from the same file on
    the target branch (usually ``main``) right now -- the safety check that
    keeps this script from ever unlabeling an issue a *later*, successfully
    merged operation already claimed. ``issue_labels`` is the candidate
    issue's current labels; pass an empty sequence if the issue number
    couldn't be resolved yet, since no label check is reachable in that
    case anyway.
    """

    if pr_state != "closed" or pr_merged:
        return ReleaseDecision(False, None, "PR is not a closed-and-unmerged intake attempt")
    if not pr_head_ref.startswith("agent-pilot/intake-"):
        return ReleaseDecision(False, None, "PR head branch is not an agent-pilot intake branch")

    issue_number = parse_source_issue(pr_head_intake_summary_source_reference, target_repo)
    if issue_number is None:
        return ReleaseDecision(
            False, None, "no resolvable source_reference on the PR's head state/intake-summary.json"
        )

    current_issue_number = parse_source_issue(main_intake_summary_source_reference, target_repo)
    if current_issue_number == issue_number:
        return ReleaseDecision(
            False,
            issue_number,
            "this issue's import is the current one on the target branch -- not stuck",
        )

    if IMPORTED_LABEL not in issue_labels:
        return ReleaseDecision(False, issue_number, "issue is not currently labeled intake:imported")

    return ReleaseDecision(True, issue_number, "abandoned intake PR left a stale intake:imported label")


def github_request_factory(token: str, api_url: str = "https://api.github.com") -> RequestJson:
    def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            api_url.rstrip("/") + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "open-study-path-release-stuck-intake-import",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise ApiError(error.code, details or error.reason) from error

    return request_json


def _read_repo_json_file(request_json: RequestJson, repository: str, path: str, ref: str) -> dict[str, Any] | None:
    try:
        result = request_json("GET", f"/repos/{repository}/contents/{path}?ref={ref}", None)
    except ApiError as error:
        if error.status == 404:
            return None
        raise
    content = base64.b64decode(result["content"]).decode("utf-8")
    return json.loads(content) if content.strip() else None


def release_stuck_intake_import(
    *, repository: str, pr_number: int, request_json: RequestJson, default_branch: str = "main"
) -> ReleaseDecision:
    pr = request_json("GET", f"/repos/{repository}/pulls/{pr_number}", None)

    pr_head_summary = _read_repo_json_file(
        request_json, repository, "state/intake-summary.json", pr["head"]["sha"]
    )
    main_summary = _read_repo_json_file(request_json, repository, "state/intake-summary.json", default_branch)

    candidate_issue_number = parse_source_issue(
        pr_head_summary.get("source_reference") if pr_head_summary else None, repository
    )
    issue_labels: list[str] = []
    if candidate_issue_number is not None:
        issue = request_json("GET", f"/repos/{repository}/issues/{candidate_issue_number}", None)
        issue_labels = [label["name"] for label in issue["labels"]]

    decision = resolve_release_action(
        pr_state=pr["state"],
        pr_merged=bool(pr.get("merged_at")),
        pr_head_ref=pr["head"]["ref"],
        target_repo=repository,
        pr_head_intake_summary_source_reference=(
            pr_head_summary.get("source_reference") if pr_head_summary else None
        ),
        main_intake_summary_source_reference=(main_summary.get("source_reference") if main_summary else None),
        issue_labels=issue_labels,
    )

    if decision.should_release:
        assert decision.issue_number is not None
        request_json(
            "DELETE",
            f"/repos/{repository}/issues/{decision.issue_number}/labels/{IMPORTED_LABEL}",
            None,
        )
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="OWNER/REPOSITORY")
    parser.add_argument("--pr", type=int, required=True, dest="pr_number")
    parser.add_argument("--token", required=True, help="GitHub token with issues:write, contents:read")
    parser.add_argument("--default-branch", default="main")
    args = parser.parse_args()

    request_json = github_request_factory(args.token)
    decision = release_stuck_intake_import(
        repository=args.repository,
        pr_number=args.pr_number,
        request_json=request_json,
        default_branch=args.default_branch,
    )
    if decision.should_release:
        print(f"Released intake:imported from issue #{decision.issue_number}: {decision.reason}")
    else:
        print(f"No action taken: {decision.reason}")
        if decision.issue_number is not None:
            print(f"(considered issue #{decision.issue_number})")
    sys.exit(0)


if __name__ == "__main__":
    main()
