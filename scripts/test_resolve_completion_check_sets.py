#!/usr/bin/env python3
"""Behavioral regressions for agent-pilot completion check-set resolution."""

from __future__ import annotations

from pathlib import Path

from resolve_completion_check_sets import (
    CHECK_NAME_TO_JOB_ID,
    load_manifest,
    required_job_ids,
    required_workflow_names,
)

EXPECTED_WORKFLOW_NAMES_BY_PHASE = {
    "bootstrap_instance": {"Validate Open Study Path", "Validate curriculum state"},
    "configure_intake": {"Validate Open Study Path", "Validate curriculum state"},
    "intake": {
        "Validate Open Study Path",
        "Validate curriculum state",
        "Validate intake completion",
    },
    "diagnostic": {
        "Validate Open Study Path",
        "Validate curriculum state",
        "Validate diagnostic completion",
    },
    "generate_proposal": {
        "Validate Open Study Path",
        "Validate curriculum state",
        "Validate proposal completion",
    },
    "generate_detailed": {
        "Validate Open Study Path",
        "Validate curriculum state",
        "Validate usable generation",
    },
    "publish": {
        "Validate Open Study Path",
        "Validate curriculum state",
        "Validate task projection",
    },
    "evaluate": {
        "Validate Open Study Path",
        "Validate curriculum state",
        "Validate usable generation",
        "Validate task projection",
    },
    "track": {
        "Validate Open Study Path",
        "Validate curriculum state",
        "Validate task projection",
    },
    "replan": {
        "Validate Open Study Path",
        "Validate curriculum state",
        "Validate task projection",
    },
}


def main() -> None:
    manifest = load_manifest(Path("instructions/manifest.yml"))

    manifest_phase_ids = {entry["id"] for entry in manifest["phases"]} - {"generate"}
    manifest_phase_ids |= {"generate_proposal", "generate_detailed"}
    assert set(EXPECTED_WORKFLOW_NAMES_BY_PHASE) == manifest_phase_ids, (
        "this test's phase list has drifted from instructions/manifest.yml -- "
        "add/remove an EXPECTED_WORKFLOW_NAMES_BY_PHASE entry to match"
    )

    for phase, expected_names in EXPECTED_WORKFLOW_NAMES_BY_PHASE.items():
        actual_names = set(required_workflow_names(manifest, phase))
        assert actual_names == expected_names, (phase, actual_names, expected_names)

        # Baseline is required by every phase in this manifest today.
        assert "Validate Open Study Path" in actual_names, phase
        assert "Validate curriculum state" in actual_names, phase

        # required_job_ids never raises KeyError for any real manifest phase --
        # every named check this manifest declares maps onto a job id the
        # agent-pilot workflow actually knows how to run inline.
        job_ids = set(required_job_ids(manifest, phase))
        assert job_ids == {CHECK_NAME_TO_JOB_ID[name] for name in expected_names}
        assert "ci-baseline-template" in job_ids, phase
        assert "ci-baseline-curriculum" in job_ids, phase

    # An unrecognized phase id is a loud KeyError, not a silent empty result.
    try:
        required_workflow_names(manifest, "not_a_real_phase")
    except KeyError:
        pass
    else:
        raise SystemExit("expected KeyError for an unknown manifest phase id")

    print("Agent-pilot completion check-set resolution regressions passed.")


if __name__ == "__main__":
    main()
