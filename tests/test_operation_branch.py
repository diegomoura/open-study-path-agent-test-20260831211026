from __future__ import annotations

import sys
from pathlib import Path
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from operation_branch import plan_branch_convergence  # noqa: E402


class OperationBranchTests(unittest.TestCase):
    def test_failures_and_intermediate_corrections_converge_on_one_branch_and_pr(self):
        journal = {
            "operation_id": "publication-study-generative-ai-v1",
            "branch": "agent/operation-publication-study-generative-ai-v1",
            "pull_request": 72,
        }
        plan = plan_branch_convergence(
            operation_id="publication-study-generative-ai-v1",
            journal=journal,
            observed_commit_count=8,
            existing_pull_request=72,
            commit_budget=1,
        )
        self.assertEqual(journal["branch"], plan.branch)
        self.assertEqual(72, plan.pull_request)
        self.assertEqual("rebuild_same_branch_single_commit", plan.action)
        self.assertEqual(1, plan.commits_before_open)

    def test_new_operation_opens_pr_only_after_validation(self):
        plan = plan_branch_convergence(
            operation_id="publication-v2",
            journal=None,
            observed_commit_count=1,
        )
        self.assertEqual("open_single_draft_pr_after_validation", plan.action)
        self.assertEqual("agent/operation-publication-v2", plan.branch)


if __name__ == "__main__":
    unittest.main()
