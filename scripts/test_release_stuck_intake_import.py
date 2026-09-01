#!/usr/bin/env python3
"""Behavioral regressions for scripts/release_stuck_intake_import.py."""

from __future__ import annotations

from release_stuck_intake_import import parse_source_issue, resolve_release_action

TARGET_REPO = "diegomoura/open-study-path-agent-test-example"
OTHER_REPO = "diegomoura/some-other-repo"


def test_parse_source_issue_requires_matching_repository() -> None:
    ref = f"github_issue:{TARGET_REPO}#3"
    assert parse_source_issue(ref, TARGET_REPO) == 3
    assert parse_source_issue(ref, OTHER_REPO) is None


def test_parse_source_issue_tolerates_missing_or_malformed() -> None:
    assert parse_source_issue(None, TARGET_REPO) is None
    assert parse_source_issue("", TARGET_REPO) is None
    assert parse_source_issue("not-a-reference", TARGET_REPO) is None
    assert parse_source_issue(f"github_issue:{TARGET_REPO}#abc", TARGET_REPO) is None


def _decide(**overrides):
    defaults = dict(
        pr_state="closed",
        pr_merged=False,
        pr_head_ref="agent-pilot/intake-20260901201455",
        target_repo=TARGET_REPO,
        pr_head_intake_summary_source_reference=f"github_issue:{TARGET_REPO}#3",
        main_intake_summary_source_reference=None,
        issue_labels=("study-request", "intake:imported"),
    )
    defaults.update(overrides)
    return resolve_release_action(**defaults)


def test_releases_the_stuck_label_for_the_canonical_case() -> None:
    # This is exactly the situation hit three times in the same real
    # dispatch session: a closed, unmerged agent-pilot intake PR whose
    # source issue is still labeled intake:imported, with no competing
    # current import on the target branch.
    decision = _decide()
    assert decision.should_release is True
    assert decision.issue_number == 3


def test_refuses_when_pr_is_open() -> None:
    decision = _decide(pr_state="open")
    assert decision.should_release is False
    assert decision.issue_number is None


def test_refuses_when_pr_was_actually_merged() -> None:
    decision = _decide(pr_state="closed", pr_merged=True)
    assert decision.should_release is False
    assert decision.issue_number is None


def test_refuses_for_a_non_intake_branch() -> None:
    decision = _decide(pr_head_ref="agent-pilot/publish-20260901201455")
    assert decision.should_release is False
    assert decision.issue_number is None


def test_refuses_without_a_resolvable_source_reference() -> None:
    decision = _decide(pr_head_intake_summary_source_reference=None)
    assert decision.should_release is False
    assert decision.issue_number is None

    decision = _decide(pr_head_intake_summary_source_reference=f"github_issue:{OTHER_REPO}#3")
    assert decision.should_release is False
    assert decision.issue_number is None


def test_refuses_when_the_issue_is_the_current_merged_import() -> None:
    # Safety check: never unlabel an issue a later, successfully merged
    # operation already claimed, even if an older abandoned PR also
    # referenced the same issue number.
    decision = _decide(main_intake_summary_source_reference=f"github_issue:{TARGET_REPO}#3")
    assert decision.should_release is False
    assert decision.issue_number == 3
    assert "not stuck" in decision.reason


def test_refuses_when_the_issue_is_not_actually_labeled() -> None:
    # Idempotent: running this twice in a row must not error the second
    # time just because there's nothing left to release.
    decision = _decide(issue_labels=("study-request",))
    assert decision.should_release is False
    assert decision.issue_number == 3


def test_a_different_current_import_does_not_block_release() -> None:
    # The target branch has since imported a *different* issue (#7) --
    # issue #3's stale label from the abandoned PR is still safe to release.
    decision = _decide(main_intake_summary_source_reference=f"github_issue:{TARGET_REPO}#7")
    assert decision.should_release is True
    assert decision.issue_number == 3


def main() -> None:
    tests = [
        test_parse_source_issue_requires_matching_repository,
        test_parse_source_issue_tolerates_missing_or_malformed,
        test_releases_the_stuck_label_for_the_canonical_case,
        test_refuses_when_pr_is_open,
        test_refuses_when_pr_was_actually_merged,
        test_refuses_for_a_non_intake_branch,
        test_refuses_without_a_resolvable_source_reference,
        test_refuses_when_the_issue_is_the_current_merged_import,
        test_refuses_when_the_issue_is_not_actually_labeled,
        test_a_different_current_import_does_not_block_release,
    ]
    for test in tests:
        test()
    print(f"release_stuck_intake_import regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
