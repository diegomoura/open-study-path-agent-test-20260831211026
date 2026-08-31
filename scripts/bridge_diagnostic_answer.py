#!/usr/bin/env python3
"""Resolve one diagnostic-answer Issue Form submission and repost it as a
comment on its diagnostic session issue.

Etapa 9d: `.github/ISSUE_TEMPLATE/diagnostic-answer.yml` always creates a new
issue (GitHub Issue Forms cannot reply into an existing issue), but the
diagnostic session/reviewer pipeline
(`.github/workflows/agent-pilot-diagnostic.yml`) only ever reads the session
issue's own comment thread. This script is the deterministic bridge between
the two: no Anthropic API call, no LLM judgment -- identity and content
extraction are handled entirely by `scripts/diagnostic_answer_resolution.py`,
this script only does the I/O (fetch, classify, comment, label, close).

Two real, sequential findings shaped how the evaluation turn actually gets
triggered after a successful import (both documented in
docs/claude-agent-pilot-etapa9d-diagnostic-answer-form.md):

1. Reposting the comment alone is not enough: GitHub does not fire
   event-triggered workflows (issue_comment included) for events caused by a
   workflow's own GITHUB_TOKEN.
2. An explicit workflow_dispatch API call, the first fix attempted, does not
   work either: GitHub structurally blocks GITHUB_TOKEN from firing
   workflow_dispatch/repository_dispatch, regardless of granted permissions.
   This is not a settings problem -- it needs a PAT, full stop -- confirmed
   by a real 403 ("Resource not accessible by integration").

Given both, this script does not try to trigger a second run of
agent-pilot-diagnostic.yml at all. It only imports the submission and
prints/exposes the resolved session issue number (via GITHUB_OUTPUT, when
running in Actions); agent-pilot-diagnostic-answer-bridge.yml's second job
calls agent-pilot-diagnostic.yml directly as a reusable workflow
(`workflow_call`, in the same run graph, not a new triggered run), which
needs no PAT or extra secret since it is not an event being fired.

Runs as `.github/workflows/agent-pilot-diagnostic-answer-bridge.yml`,
triggered by `issues: [opened]` on issues carrying the `diagnostic:answer`
label.
"""

from __future__ import annotations

import argparse
import os

from diagnostic_answer_resolution import (
    IMPORTED_LABEL,
    AnswerIssue,
    classify_answer_issue,
    extract_session_issue_number,
    render_answers_as_comment,
    render_rejection_comment,
)
from ensure_repository_labels import ApiError, github_request_factory


def _fetch_issue(request_json, repository: str, number: int) -> dict | None:
    try:
        return request_json("GET", f"/repos/{repository}/issues/{number}", None)
    except ApiError as error:
        if error.status == 404:
            return None
        raise


def _write_github_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return  # not running in Actions (e.g. under test) -- nothing to write
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="owner/repo, from GITHUB_REPOSITORY")
    parser.add_argument("--answer-issue-number", required=True, type=int)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    request_json = github_request_factory(token, api_url)

    raw = _fetch_issue(request_json, args.repository, args.answer_issue_number)
    if raw is None:
        raise SystemExit(f"answer issue #{args.answer_issue_number} not found -- nothing to bridge")

    answer_issue = AnswerIssue(
        number=raw["number"],
        title=raw.get("title", ""),
        body=raw.get("body") or "",
        labels=frozenset(label.get("name", "") for label in raw.get("labels", [])),
        is_pull_request="pull_request" in raw,
        author_login=(raw.get("user") or {}).get("login"),
    )

    # Pre-parse just the session number so we know whether to even attempt a
    # lookup -- classify_answer_issue() re-derives this itself (pure, no I/O);
    # this call is only to decide whether session_lookup_failed applies below.
    session_number = extract_session_issue_number(answer_issue.body)
    session_labels: frozenset[str] | None = None
    session_lookup_failed = False
    if session_number is not None:
        session_raw = _fetch_issue(request_json, args.repository, session_number)
        if session_raw is None:
            session_lookup_failed = True
        else:
            session_labels = frozenset(label.get("name", "") for label in session_raw.get("labels", []))

    decision = classify_answer_issue(
        answer_issue,
        session_labels=session_labels,
        session_lookup_failed=session_lookup_failed,
    )

    if not decision.accepted:
        print(f"answer issue #{answer_issue.number} rejected: {', '.join(decision.reasons)}")
        request_json(
            "POST",
            f"/repos/{args.repository}/issues/{answer_issue.number}/comments",
            {"body": render_rejection_comment(decision)},
        )
        _write_github_output("session_issue_number", "")
        return

    comment_body = render_answers_as_comment(decision.answers)
    request_json(
        "POST",
        f"/repos/{args.repository}/issues/{decision.session_issue_number}/comments",
        {"body": comment_body},
    )
    request_json(
        "POST",
        f"/repos/{args.repository}/issues/{answer_issue.number}/labels",
        {"labels": [IMPORTED_LABEL]},
    )
    request_json(
        "PATCH",
        f"/repos/{args.repository}/issues/{answer_issue.number}",
        {"state": "closed"},
    )

    # Does NOT try to trigger agent-pilot-diagnostic.yml itself -- see the
    # module docstring for why (both a plain repost and an explicit
    # workflow_dispatch call were tried against a real instance and both
    # failed for structural GITHUB_TOKEN reasons, not fixable from here).
    # Exposing the session issue number as a job output is enough:
    # agent-pilot-diagnostic-answer-bridge.yml's second job reads it and
    # calls agent-pilot-diagnostic.yml directly as a reusable workflow.
    _write_github_output("session_issue_number", str(decision.session_issue_number))
    print(
        f"imported answer issue #{answer_issue.number} "
        f"({len(decision.answers)} answers) into session issue #{decision.session_issue_number}"
    )


if __name__ == "__main__":
    main()
