#!/usr/bin/env python3
"""Behavioral regressions for the agent-pilot post-merge digest (Opcao C)."""

from __future__ import annotations

from pathlib import Path
import tempfile

from agent_pilot_merge_digest import (
    build_digest,
    load_latest_usage_record,
    parse_source_issue_number,
)


def test_parses_valid_source_reference_for_matching_repo() -> None:
    number = parse_source_issue_number(
        "github_issue:diegomoura/open-study-path-agent-test-20260826011447#42",
        expected_repo="diegomoura/open-study-path-agent-test-20260826011447",
    )
    assert number == 42


def test_rejects_source_reference_for_a_different_repo() -> None:
    number = parse_source_issue_number(
        "github_issue:someone-else/other-repo#42",
        expected_repo="diegomoura/open-study-path-agent-test-20260826011447",
    )
    assert number is None


def test_rejects_missing_or_malformed_source_reference() -> None:
    assert parse_source_issue_number(None, expected_repo="a/b") is None
    assert parse_source_issue_number("", expected_repo="a/b") is None
    assert parse_source_issue_number("not-a-real-reference", expected_repo="a/b") is None
    assert parse_source_issue_number("github_issue:a/b#not-a-number", expected_repo="a/b") is None


def test_load_latest_usage_record_picks_the_most_recent_matching_phase_line() -> None:
    with tempfile.TemporaryDirectory() as directory:
        jsonl_path = Path(directory) / "state" / "agent-pilot-usage.jsonl"
        jsonl_path.parent.mkdir(parents=True)
        jsonl_path.write_text(
            "\n".join(
                [
                    '{"phase": "intake", "combined_tokens": 1000, "combined_estimated_cost_usd": 0.01}',
                    '{"phase": "publish", "combined_tokens": 2000, "combined_estimated_cost_usd": 0.02}',
                    '{"phase": "intake", "combined_tokens": 3000, "combined_estimated_cost_usd": 0.03}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        record = load_latest_usage_record(jsonl_path, phase="intake")
        assert record is not None
        assert record["combined_tokens"] == 3000


def test_load_latest_usage_record_returns_none_when_file_or_phase_missing() -> None:
    with tempfile.TemporaryDirectory() as directory:
        missing_path = Path(directory) / "state" / "agent-pilot-usage.jsonl"
        assert load_latest_usage_record(missing_path, phase="intake") is None

        existing_path = Path(directory) / "state" / "agent-pilot-usage.jsonl"
        existing_path.parent.mkdir(parents=True)
        existing_path.write_text('{"phase": "publish"}\n', encoding="utf-8")
        assert load_latest_usage_record(existing_path, phase="intake") is None


def test_build_digest_includes_cost_findings_and_artifacts() -> None:
    review_document = {
        "blocking_findings": [],
        "non_blocking_findings": ["consider tightening the rubric wording"],
        "artifacts": [
            {"path": "study.config.yml", "change": "current"},
            {"path": "study/roadmap.md", "change": "current"},
            {"path": "study/old-topic.md", "change": "deleted"},
        ],
    }
    usage_record = {"combined_tokens": 12345, "combined_estimated_cost_usd": 0.4321}

    markdown = build_digest(
        phase="intake",
        target_repo="diegomoura/open-study-path-agent-test-20260826011447",
        pr_number=7,
        review_document=review_document,
        usage_record=usage_record,
    )

    assert "PR #7" in markdown
    assert "$0.4321" in markdown
    assert "12345 tokens" in markdown
    assert "consider tightening the rubric wording" in markdown
    assert "`study.config.yml`" in markdown
    assert "`study/old-topic.md` (deleted)" in markdown


def test_build_digest_handles_missing_usage_and_no_findings() -> None:
    review_document = {
        "blocking_findings": [],
        "non_blocking_findings": [],
        "artifacts": [],
    }
    markdown = build_digest(
        phase="diagnostic",
        target_repo="owner/repo",
        pr_number=3,
        review_document=review_document,
        usage_record=None,
    )
    assert "unknown (no usage record found for this phase)" in markdown
    assert "No non-blocking findings" in markdown
    assert "No artifacts listed" in markdown


def main() -> None:
    test_parses_valid_source_reference_for_matching_repo()
    test_rejects_source_reference_for_a_different_repo()
    test_rejects_missing_or_malformed_source_reference()
    test_load_latest_usage_record_picks_the_most_recent_matching_phase_line()
    test_load_latest_usage_record_returns_none_when_file_or_phase_missing()
    test_build_digest_includes_cost_findings_and_artifacts()
    test_build_digest_handles_missing_usage_and_no_findings()
    print("Agent-pilot post-merge digest regressions passed.")


if __name__ == "__main__":
    main()
