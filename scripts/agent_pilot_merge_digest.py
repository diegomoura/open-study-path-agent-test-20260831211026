#!/usr/bin/env python3
"""Build the post-merge digest comment for the agent-pilot auto-merge gate.

Design requirement (see the handoff this implements, "Opcao C", Frente 1):
this digest must never cost an API call. Every field it reports already
exists on disk, written earlier by the real author/reviewer run:

- the reviewer's own findings, from ``state/reviews/agent-pilot-<phase>.yml``
  (``scripts/review_framework.py`` / ``templates/review.yml``);
- the real token/cost usage for this run, the most recent matching entry in
  ``state/agent-pilot-usage.jsonl`` (``scripts/summarize_agent_pilot_usage.py``);
- the changed artifacts list, from the same review artifact's ``artifacts:``;
- the originating issue number, parsed from
  ``state/intake-summary.json``'s ``source_reference`` (format
  ``github_issue:<owner>/<repo>#<number>``, written by
  ``scripts/agent_runtime.py`` -- see instructions/10-intake.md). This field
  already existed; no new tracking had to be added anywhere.

This module only builds text and resolves the issue number to comment on.
Actually posting the comment is the workflow's job (``gh issue comment``),
kept out of this module so it stays testable without any network access.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SOURCE_REFERENCE_PATTERN = re.compile(r"^github_issue:(?P<repo>[^#]+)#(?P<number>\d+)$")


@dataclass(frozen=True)
class Digest:
    markdown: str
    source_issue_number: int | None


def parse_source_issue_number(source_reference: Any, *, expected_repo: str) -> int | None:
    """Return the originating issue number, only if it belongs to this repo.

    A missing, malformed, or cross-repo source_reference returns None rather
    than raising -- a digest with no originating issue to post to is still a
    valid outcome (e.g. an instance whose intake summary predates this field,
    or a phase that never went through GitHub-Issues intake at all), it just
    means the workflow logs the digest instead of posting it anywhere.
    """
    if not isinstance(source_reference, str):
        return None
    match = SOURCE_REFERENCE_PATTERN.match(source_reference.strip())
    if not match:
        return None
    if match.group("repo") != expected_repo:
        return None
    return int(match.group("number"))


def load_latest_usage_record(jsonl_path: Path, *, phase: str) -> Mapping[str, Any] | None:
    """Return the most recent state/agent-pilot-usage.jsonl entry for this phase."""
    if not jsonl_path.is_file():
        return None
    latest: Mapping[str, Any] | None = None
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("phase") == phase:
            latest = record  # later lines win; the file is append-only
    return latest


def _format_cost(usage_record: Mapping[str, Any] | None) -> str:
    if usage_record is None:
        return "unknown (no usage record found for this phase)"
    cost = usage_record.get("combined_estimated_cost_usd")
    tokens = usage_record.get("combined_tokens")
    if cost is None or tokens is None:
        return "unknown (incomplete usage record)"
    return f"${cost:.4f} ({tokens} tokens)"


def _format_artifacts(review_document: Mapping[str, Any]) -> list[str]:
    lines = []
    for entry in review_document.get("artifacts") or []:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path", "<unknown>")
        change = entry.get("change", "current")
        lines.append(f"- `{path}`" + (" (deleted)" if change == "deleted" else ""))
    return lines


def build_digest(
    *,
    phase: str,
    target_repo: str,
    pr_number: int,
    review_document: Mapping[str, Any],
    usage_record: Mapping[str, Any] | None,
) -> str:
    blocking = list(review_document.get("blocking_findings") or [])
    non_blocking = list(review_document.get("non_blocking_findings") or [])
    artifact_lines = _format_artifacts(review_document)

    lines = [
        f"## Agent pilot auto-merge digest -- `{phase}`",
        "",
        f"PR #{pr_number} for `{target_repo}` was merged automatically: the independent "
        "reviewer approved the run and every required check succeeded "
        "(Opcao C -- see docs/claude-agent-pilot.md).",
        "",
        f"**Estimated cost:** {_format_cost(usage_record)}. Planning estimate only -- "
        "check the Anthropic Console for real billed usage.",
        "",
    ]

    if blocking:
        # Should not normally be reachable here (a merge only happens when
        # the reviewer approved, and an approved review cannot carry blocking
        # findings -- see review_framework.validate_review_document). Kept
        # anyway so a future review-artifact bug fails loudly in the digest
        # instead of silently reporting a clean merge.
        lines.append("**Blocking findings recorded despite merge (this should not happen):**")
        lines.extend(f"- {finding}" for finding in blocking)
        lines.append("")

    if non_blocking:
        lines.append("**Non-blocking findings from the independent review:**")
        lines.extend(f"- {finding}" for finding in non_blocking)
        lines.append("")
    else:
        lines.append("No non-blocking findings from the independent review.")
        lines.append("")

    if artifact_lines:
        lines.append("**Artifacts changed:**")
        lines.extend(artifact_lines)
    else:
        lines.append("No artifacts listed on the review artifact.")

    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--target-repo", required=True, help="OWNER/REPOSITORY, for source_reference matching")
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument(
        "--review-artifact",
        required=True,
        help="Path to state/reviews/agent-pilot-<phase>.yml",
    )
    parser.add_argument(
        "--usage-log",
        default="state/agent-pilot-usage.jsonl",
        help="Path to the running usage log",
    )
    parser.add_argument(
        "--intake-summary",
        default="state/intake-summary.json",
        help="Path to state/intake-summary.json, used to resolve the originating issue",
    )
    parser.add_argument("--out-digest", required=True, help="Where to write the digest markdown")
    args = parser.parse_args()

    import yaml

    review_document = yaml.safe_load(Path(args.review_artifact).read_text(encoding="utf-8")) or {}
    usage_record = load_latest_usage_record(Path(args.usage_log), phase=args.phase)

    source_issue_number = None
    intake_summary_path = Path(args.intake_summary)
    if intake_summary_path.is_file():
        try:
            intake_summary = json.loads(intake_summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            intake_summary = {}
        source_issue_number = parse_source_issue_number(
            intake_summary.get("source_reference"), expected_repo=args.target_repo
        )

    digest_markdown = build_digest(
        phase=args.phase,
        target_repo=args.target_repo,
        pr_number=args.pr_number,
        review_document=review_document,
        usage_record=usage_record,
    )

    Path(args.out_digest).write_text(digest_markdown, encoding="utf-8")
    print(f"source_issue_number={source_issue_number if source_issue_number is not None else ''}")


if __name__ == "__main__":
    main()
