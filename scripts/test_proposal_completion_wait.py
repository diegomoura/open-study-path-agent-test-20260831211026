#!/usr/bin/env python3
"""Structural regression for automatic completion wiring."""

from pathlib import Path

import yaml


AUTOMATIC_POLICIES = {"auto_when_unambiguous", "agent_review_then_merge"}
EXPECTED_CHECK_SETS = {
    "baseline",
    "intake",
    "diagnostic",
    "proposal",
    "usable_generation",
    "task_projection",
}


def main() -> None:
    manifest = yaml.safe_load(Path("instructions/manifest.yml").read_text(encoding="utf-8"))
    completion = manifest.get("automatic_completion") or {}

    assert completion.get("execution_contract") == "instructions/03-await-ci-and-merge.md"
    assert completion.get("state_machine") == "scripts/ci_completion_state.py"
    assert set(completion.get("automatic_merge_policies") or []) == AUTOMATIC_POLICIES

    check_sets = completion.get("check_sets") or {}
    assert EXPECTED_CHECK_SETS <= set(check_sets), check_sets
    assert all(check_sets[name] for name in EXPECTED_CHECK_SETS)

    declared_checks = {
        check_name
        for check_set in check_sets.values()
        for check_name in check_set
    }
    workflow_names = set()
    for workflow_path in Path(".github/workflows").glob("*.yml"):
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8")) or {}
        if isinstance(workflow.get("name"), str):
            workflow_names.add(workflow["name"])
    missing_workflows = sorted(declared_checks - workflow_names)
    assert not missing_workflows, "manifest checks without matching workflow names: " + ", ".join(missing_workflows)

    phases = {phase["id"]: phase for phase in manifest["phases"]}
    assert all(phase.get("completion_check_sets") for phase in phases.values())

    generate = phases["generate"]
    suboperations = generate.get("suboperations") or {}
    assert suboperations["proposal"]["completion_check_sets"] == ["baseline", "proposal"]
    assert suboperations["detailed_generation"]["completion_check_sets"] == [
        "baseline",
        "usable_generation",
    ]

    for phase in phases.values():
        for name in phase["completion_check_sets"]:
            assert name in check_sets, (phase["id"], name)

    contract = Path("instructions/03-await-ci-and-merge.md").read_text(encoding="utf-8")
    ready_position = contract.index("Mark the pull request ready")
    auto_merge_position = contract.index("enable auto-merge only after")
    assert ready_position < auto_merge_position
    assert "`expected_head_sha` as the atomic precondition" in contract
    assert "Do not commit timing metrics" in contract
    assert "operation-specific checks" in contract

    shared = Path("instructions/phase-completion.md").read_text(encoding="utf-8")
    assert "This requirement applies to every lifecycle phase and suboperation" in shared
    assert "scripts/ci_completion_state.py" in shared

    proposal = Path("instructions/28-propose-path.md").read_text(encoding="utf-8")
    assert "instructions/03-await-ci-and-merge.md" in proposal
    assert "Do not end the learner interaction merely because CI is still running" in proposal

    print("Automatic completion wiring regression passed.")


if __name__ == "__main__":
    main()
