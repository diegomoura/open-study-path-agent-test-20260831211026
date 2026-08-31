#!/usr/bin/env python3
"""Combine author + reviewer token usage into one summary for the pilot workflow.

Both scripts/agent_runtime.py CLI calls print their own {"usage": {...}} block
(see agent_runtime.py's UsageTotals). This just adds the two together and
computes a combined cost estimate, so the workflow has one number to put in
the PR body and one line to append to the running cost log
(state/agent-pilot-usage.jsonl) -- the log is what lets a course creator look
back later and answer "how much did generating my course actually cost?"
without digging through Action run logs one at a time.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def combine(author_result: dict, reviewer_result: dict | None = None) -> dict:
    author_usage = author_result.get("usage", {})
    has_reviewer = reviewer_result is not None
    reviewer_usage = (reviewer_result or {}).get("usage", {})
    author_cost = author_usage.get("estimated_cost_usd")
    reviewer_cost = reviewer_usage.get("estimated_cost_usd")
    combined_cost = None
    if author_cost is not None and reviewer_cost is not None:
        combined_cost = author_cost + reviewer_cost
    elif author_cost is not None:
        # Author-only record (e.g. a non-terminal diagnostic turn, which
        # never involves a reviewer call at all -- see
        # docs/claude-agent-pilot-etapa14-diagnostic-usage-ledger.md). The
        # combined cost is simply the author's real cost, not unknown.
        combined_cost = author_cost

    summary = {
        "author": {"model": author_result.get("model"), **author_usage},
        "combined_tokens": (
            author_usage.get("total_tokens", 0) + reviewer_usage.get("total_tokens", 0)
        ),
        "combined_estimated_cost_usd": combined_cost,
    }
    if has_reviewer:
        summary["reviewer"] = {"model": reviewer_result.get("model"), **reviewer_usage}
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author-result", required=True)
    parser.add_argument(
        "--reviewer-result",
        default=None,
        help="Omit for an author-only record (e.g. a non-terminal diagnostic turn, which never calls a reviewer)",
    )
    parser.add_argument("--phase", required=True)
    parser.add_argument("--target-repo", required=True)
    parser.add_argument("--out-summary-json", required=True)
    parser.add_argument("--append-log", default=None, help="Path to a JSONL cost log to append one record to")
    args = parser.parse_args()

    reviewer_result = _load(args.reviewer_result) if args.reviewer_result else None
    summary = combine(_load(args.author_result), reviewer_result)
    summary["phase"] = args.phase
    summary["target_repo"] = args.target_repo
    summary["recorded_at"] = datetime.now(timezone.utc).isoformat()

    Path(args.out_summary_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if args.append_log:
        log_path = Path(args.append_log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary) + "\n")


if __name__ == "__main__":
    main()
