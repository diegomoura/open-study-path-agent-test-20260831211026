#!/usr/bin/env python3
"""Behavioral regressions for scripts/summarize_agent_pilot_usage.py."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile

from summarize_agent_pilot_usage import combine

AUTHOR_RESULT = {
    "model": "claude-sonnet-5",
    "usage": {
        "input_tokens": 100,
        "output_tokens": 200,
        "total_tokens": 300,
        "estimated_cost_usd": 0.01,
    },
}
REVIEWER_RESULT = {
    "model": "claude-sonnet-5",
    "usage": {
        "input_tokens": 50,
        "output_tokens": 60,
        "total_tokens": 110,
        "estimated_cost_usd": 0.02,
    },
}


def test_combine_with_reviewer_sums_both_costs_and_tokens() -> None:
    summary = combine(AUTHOR_RESULT, REVIEWER_RESULT)
    assert summary["combined_tokens"] == 300 + 110
    assert summary["combined_estimated_cost_usd"] == 0.03
    assert summary["reviewer"]["model"] == "claude-sonnet-5"
    assert summary["author"]["model"] == "claude-sonnet-5"


def test_combine_without_reviewer_is_author_only() -> None:
    # This is the case that was previously missing entirely: a non-terminal
    # diagnostic turn, which makes a real, billed author-only API call and
    # never calls a reviewer at all.
    summary = combine(AUTHOR_RESULT, None)
    assert summary["combined_tokens"] == 300
    assert summary["combined_estimated_cost_usd"] == 0.01
    assert "reviewer" not in summary, "an author-only record must not claim a reviewer ran"


def test_cli_appends_an_author_only_record_when_reviewer_result_is_omitted() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        author_path = root / "author-result.json"
        author_path.write_text(json.dumps(AUTHOR_RESULT), encoding="utf-8")
        out_summary = root / "usage-summary.json"
        log_path = root / "state" / "agent-pilot-usage.jsonl"

        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent / "summarize_agent_pilot_usage.py"),
                "--author-result",
                str(author_path),
                "--phase",
                "diagnostic",
                "--target-repo",
                "owner/repo",
                "--out-summary-json",
                str(out_summary),
                "--append-log",
                str(log_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr

        record = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert record["phase"] == "diagnostic"
        assert "reviewer" not in record
        assert record["combined_estimated_cost_usd"] == 0.01


def test_cli_still_appends_a_combined_record_when_reviewer_result_is_given() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        author_path = root / "author-result.json"
        author_path.write_text(json.dumps(AUTHOR_RESULT), encoding="utf-8")
        reviewer_path = root / "reviewer-result.json"
        reviewer_path.write_text(json.dumps(REVIEWER_RESULT), encoding="utf-8")
        out_summary = root / "usage-summary.json"
        log_path = root / "state" / "agent-pilot-usage.jsonl"

        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent / "summarize_agent_pilot_usage.py"),
                "--author-result",
                str(author_path),
                "--reviewer-result",
                str(reviewer_path),
                "--phase",
                "diagnostic",
                "--target-repo",
                "owner/repo",
                "--out-summary-json",
                str(out_summary),
                "--append-log",
                str(log_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr

        record = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert record["reviewer"]["model"] == "claude-sonnet-5"
        assert record["combined_estimated_cost_usd"] == 0.03


def main() -> None:
    test_combine_with_reviewer_sums_both_costs_and_tokens()
    test_combine_without_reviewer_is_author_only()
    test_cli_appends_an_author_only_record_when_reviewer_result_is_omitted()
    test_cli_still_appends_a_combined_record_when_reviewer_result_is_given()
    print("Agent-pilot usage summarizer regressions passed.")


if __name__ == "__main__":
    main()
