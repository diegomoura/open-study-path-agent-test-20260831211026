#!/usr/bin/env python3
"""Assemble the diagnostic session's running transcript for the author prompt.

Etapa 4b (docs/claude-agent-pilot-etapa4b-diagnostic-design.md): each
diagnostic turn is a fresh, isolated `run_agent()` call with no memory of
earlier turns. This script is what lets it reconstruct the whole running
Q&A exchange -- issue body (the original intake/diagnostic context) plus
every comment posted so far, in order -- from the GitHub issue thread
itself, the same "context from artifacts, never memory" discipline every
other phase in this harness already follows.

Kept as its own script, not inline `python -c` in the workflow YAML, for the
same reason scripts/format_pr_body.py and scripts/publish_author_summary.py
are their own scripts.
"""

from __future__ import annotations

import argparse
import os

from ensure_repository_labels import github_request_factory


def render_transcript(issue_number: int, issue_title: str, issue_body: str, comments: list[dict]) -> str:
    lines = [
        f"Diagnostic session issue: #{issue_number} -- {issue_title}",
        "",
        "## Original session context (issue body)",
        "",
        issue_body or "(empty)",
        "",
    ]
    if comments:
        lines.append(f"## Comment thread so far ({len(comments)} comments, chronological)")
        lines.append("")
        for index, comment in enumerate(comments, start=1):
            author = comment.get("author_login") or "?"
            body = comment.get("body") or ""
            lines.append(f"### Comment {index} (by {author})")
            lines.append("")
            lines.append(body)
            lines.append("")
    else:
        lines.append("## Comment thread so far")
        lines.append("")
        lines.append("(no comments yet -- this is the first turn of the session)")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="owner/repo, from GITHUB_REPOSITORY")
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--out", required=True, help="path to write the rendered transcript")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    request_json = github_request_factory(token, api_url)

    issue = request_json("GET", f"/repos/{args.repository}/issues/{args.issue_number}", None)
    raw_comments = request_json(
        "GET", f"/repos/{args.repository}/issues/{args.issue_number}/comments?per_page=100", None
    )
    comments = [
        {
            "author_login": (item.get("user") or {}).get("login"),
            "created_at": item.get("created_at"),
            "body": item.get("body") or "",
        }
        for item in raw_comments or []
    ]

    transcript = render_transcript(args.issue_number, issue.get("title", ""), issue.get("body") or "", comments)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(transcript)
    print(f"wrote diagnostic transcript ({len(comments)} comments) to {args.out}")


if __name__ == "__main__":
    main()
