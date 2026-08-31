#!/usr/bin/env python3
"""Resolve which named completion checks a manifest phase requires.

Pure logic lives in ``required_workflow_names`` -- it only reads
``instructions/manifest.yml``'s ``automatic_completion.check_sets`` and each
phase's (or suboperation's) ``completion_check_sets``, exactly the same data
``scripts/ci_completion_state.py`` and ``scripts/test_proposal_completion_wait.py``
already treat as authoritative for the older instructions-driven pipeline.

This script reuses that same manifest data for a second, independent
pipeline: the agent-pilot workflow's auto-merge gate
(``.github/workflows/agent-pilot-setup.yml``). Rather than waiting on
external ``pull_request``-triggered check runs (which a GITHUB_TOKEN-authored
pull request never receives -- GitHub does not cascade events caused by the
default token), that workflow calls the same six validation workflows inline
as reusable workflows (``workflow_call``). This script tells it which of the
six are actually required for the phase being merged, so the four
suboperation-specific checks are not run when they are not part of the
phase's ``completion_check_sets``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping

import yaml

MANIFEST_PATH = Path("instructions/manifest.yml")

# Maps each named check (as declared in manifest.yml's check_sets) to the
# agent-pilot-setup.yml job id that runs it. "baseline" checks are required by
# every phase today, so their two job ids are not exposed as a GITHUB_OUTPUT
# flag -- the workflow always runs them -- but resolve() still returns them,
# and test coverage still asserts they are always present.
CHECK_NAME_TO_JOB_ID: dict[str, str] = {
    "Validate Open Study Path": "ci-baseline-template",
    "Validate curriculum state": "ci-baseline-curriculum",
    "Validate intake completion": "ci-intake",
    "Validate diagnostic completion": "ci-diagnostic",
    "Validate proposal completion": "ci-proposal",
    "Validate usable generation": "ci-usable-generation",
    "Validate task projection": "ci-task-projection",
}

# Job ids that are always required (never gated by an `if:` in the workflow),
# so the CLI does not need to emit a needs_* flag for them.
ALWAYS_REQUIRED_JOB_IDS = frozenset({"ci-baseline-template", "ci-baseline-curriculum"})

# Manifest phase ids that are not top-level phases.yml entries but
# suboperations of the `generate` phase, and the suboperation key under
# `generate.suboperations` each one resolves to.
GENERATE_SUBOPERATIONS: dict[str, str] = {
    "generate_proposal": "proposal",
    "generate_detailed": "detailed_generation",
}


def load_manifest(path: Path = MANIFEST_PATH) -> Mapping:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _phase_completion_check_sets(manifest: Mapping, phase: str) -> tuple[str, ...]:
    phases = {entry["id"]: entry for entry in manifest["phases"]}

    suboperation_key = GENERATE_SUBOPERATIONS.get(phase)
    if suboperation_key is not None:
        generate_phase = phases["generate"]
        suboperation = generate_phase["suboperations"][suboperation_key]
        return tuple(suboperation["completion_check_sets"])

    if phase not in phases:
        raise KeyError(f"unknown manifest phase: {phase}")
    return tuple(phases[phase]["completion_check_sets"])


def required_workflow_names(manifest: Mapping, phase: str) -> tuple[str, ...]:
    """Return every named check (workflow name) the phase's manifest entry requires.

    Order is preserved from the manifest, duplicates across check sets are
    dropped, but the set can otherwise contain any name declared under
    ``automatic_completion.check_sets`` -- this function does not assume the
    six checks the agent-pilot workflow currently knows how to run inline;
    that assumption is the CLI's job (``required_job_ids``), so a manifest
    check set this script does not recognize is a loud ``KeyError`` here,
    never a silently-skipped check.
    """
    check_sets = manifest["automatic_completion"]["check_sets"]
    check_set_names = _phase_completion_check_sets(manifest, phase)

    seen: set[str] = set()
    ordered: list[str] = []
    for check_set_name in check_set_names:
        for workflow_name in check_sets[check_set_name]:
            if workflow_name not in seen:
                seen.add(workflow_name)
                ordered.append(workflow_name)
    return tuple(ordered)


def required_job_ids(manifest: Mapping, phase: str) -> tuple[str, ...]:
    """Map required workflow names onto agent-pilot-setup.yml job ids.

    Raises KeyError if the phase requires a named check this workflow does
    not yet know how to run inline -- an unrecognized required check must
    block the auto-merge design, not be silently treated as satisfied.
    """
    names = required_workflow_names(manifest, phase)
    return tuple(CHECK_NAME_TO_JOB_ID[name] for name in names)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, help="Manifest phase id, e.g. intake, generate_detailed")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH))
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    job_ids = set(required_job_ids(manifest, args.phase))

    # Emit one needs_<suffix> flag per optional job id, in GITHUB_OUTPUT
    # format. The two always-required baseline jobs are omitted -- the
    # workflow runs them unconditionally.
    for job_id, suffix in (
        ("ci-intake", "intake"),
        ("ci-diagnostic", "diagnostic"),
        ("ci-proposal", "proposal"),
        ("ci-usable-generation", "usable_generation"),
        ("ci-task-projection", "task_projection"),
    ):
        flag = "true" if job_id in job_ids else "false"
        print(f"needs_{suffix}={flag}")

    # Sanity-check the two always-required baseline jobs really are required
    # for every phase -- if a future manifest change ever drops "baseline"
    # from some phase's completion_check_sets, fail loudly here rather than
    # silently skip real validation.
    missing_baseline = ALWAYS_REQUIRED_JOB_IDS - job_ids
    if missing_baseline:
        raise SystemExit(
            "phase "
            f"{args.phase!r} does not require baseline checks {sorted(missing_baseline)}; "
            "resolve_completion_check_sets.py assumes every phase always requires them -- "
            "update ALWAYS_REQUIRED_JOB_IDS or the workflow's unconditional ci-baseline-* jobs"
        )


if __name__ == "__main__":
    main()
