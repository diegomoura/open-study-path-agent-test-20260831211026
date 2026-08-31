#!/usr/bin/env python3
"""Format the pull request body for the agent pilot workflow.

Exists so the workflow YAML never has to embed a multi-line Python string
inside a `run: |` block -- that pattern is a recurring source of YAML
indentation bugs (see git history of .github/workflows/agent-pilot-setup.yml).
One small script, one job.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer-result", required=True)
    parser.add_argument("--usage-summary", required=True)
    parser.add_argument(
        "--model-config-warning",
        default="state/reviews/model-config-warnings.md",
        help="Path to the structural model-tier warning note, if model_config_review_note.py wrote one",
    )
    args = parser.parse_args()

    reviewer_result = json.loads(Path(args.reviewer_result).read_text(encoding="utf-8"))
    usage_summary = json.loads(Path(args.usage_summary).read_text(encoding="utf-8"))

    status = reviewer_result["status"]
    cost = usage_summary.get("combined_estimated_cost_usd")
    cost_str = f"${cost:.4f}" if cost is not None else "unknown"
    author_model = usage_summary["author"]["model"]
    reviewer_model = usage_summary["reviewer"]["model"]
    total_tokens = usage_summary["combined_tokens"]

    body = f"""Author and reviewer ran as two isolated Claude API calls (see docs/claude-agent-pilot.md). Reviewer status: **{status}**. This pilot does not auto-merge -- please review before merging.

Combined usage: {total_tokens} tokens (author model {author_model}, reviewer model {reviewer_model}) -- estimated cost {cost_str}. This is an estimate for planning only; check the Anthropic Console for actual billed usage. Full breakdown appended to `state/agent-pilot-usage.jsonl`.
"""

    warning_path = Path(args.model_config_warning)
    if warning_path.is_file():
        body += f"\n---\n\n{warning_path.read_text(encoding='utf-8')}"

    print(body)


if __name__ == "__main__":
    main()
