#!/usr/bin/env python3
"""Behavioral tests for the instance operation scope guard."""

from __future__ import annotations

from validate_instance_operation_scope import (
    commit_budget_error,
    is_curriculum,
    is_protected,
)


def main() -> None:
    assert is_protected("scripts/validate_curriculum.py")
    assert is_protected("instructions/32-generation-execution.md")
    assert is_protected(".github/workflows/validate-template.yml")
    assert is_protected("AGENTS.md")
    assert not is_protected("study/modules/TOPIC-001.md")

    assert is_curriculum("study/topics/TOPIC-001.md")
    assert is_curriculum("study/modules/TOPIC-001.md")
    assert is_curriculum(".github/ISSUE_TEMPLATE/assessment-topic-001.yml")
    assert not is_curriculum("state/reviews/generate-v1.yml")

    assert commit_budget_error(7, 20) is None
    assert commit_budget_error(8, 8) is None
    assert commit_budget_error(65, 52) is not None

    print("Instance operation scope guard regressions passed.")


if __name__ == "__main__":
    main()
