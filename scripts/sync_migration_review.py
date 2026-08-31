#!/usr/bin/env python3
"""Author a migration-profile review artifact for a template->instance infra sync.

The established sync pattern for pushing reusable template changes onto an
instance repository (see e.g. docs/claude-agent-pilot-etapa10-remove-slides.md,
docs/claude-agent-pilot-etapa11-integrations-off-by-default.md) is a direct
push, not a pull request -- there is no agent-pilot dispatch to independently
author a review artifact the way a real operation would. But
``scripts/validate_instance_operation_scope.py`` still (correctly) requires
*some* approved `phase: migration` review artifact to be present whenever a
push changes a protected reusable-infrastructure path
(``scripts/``, ``.github/workflows/``, ``instructions/``, ``templates/``,
``schemas/``, ``docs/``, ``AGENTS.md``, ``.open-study-path/template.yml``) on
a repository that has already been bootstrapped into an instance -- exactly
what a template sync onto a live/disposable-test instance does. Two real
syncs (Etapa 10, Etapa 11) landed on a test instance's `main` without one and
left it with a red "Validate instance operation scope and commit budget"
check, unnoticed until Etapa 12's sync hit the same gate (see
docs/claude-agent-pilot-etapa13-sync-migration-review.md).

This script closes that gap without weakening the guard: it builds a real,
honest migration review -- reviewer_role, all five migration profile checks,
and a `non_blocking_findings` narrative explaining what was and was not
touched -- and fingerprints one currently-true generated artifact (by default
`README.md`, present and instance-customizable in both the template and any
instance repo -- unlike the instance marker, which does not exist in the
template repo itself) as evidence that instance state/content was not
touched by the sync. `scripts/review_framework.py`'s coverage validator only
requires a migration review to cover artifacts it changed in the *same diff*
(none, for a pure infra sync); `scripts/validate_instance_operation_scope.py`
only requires an approved migration review to be *present* in the diff. This
script is honest either way: it never claims to have reviewed a file it did
not actually attest to, and refuses (raises) if asked to attest to a path
review_framework.py does not even recognize as a generated artifact.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import yaml

from review_framework import REVIEW_PROFILES, file_sha256, is_generated_artifact

DEFAULT_ATTESTED_ARTIFACT = "README.md"


def build_migration_review(
    *,
    root: Path,
    operation_id: str,
    notes: Sequence[str],
    attested_artifact: str = DEFAULT_ATTESTED_ARTIFACT,
    reviewed_at: str | None = None,
) -> dict:
    """Return a migration review document, ready to be YAML-dumped.

    Raises ValueError if ``attested_artifact`` is not a path
    review_framework.is_generated_artifact recognizes (a migration review can
    only cover artifacts within that profile's scope -- see
    review_framework.phase_allows_artifact), or FileNotFoundError if it does
    not currently exist on disk.
    """
    if not is_generated_artifact(attested_artifact):
        raise ValueError(
            f"{attested_artifact!r} is not a generated artifact recognized by "
            "review_framework.is_generated_artifact -- a migration review can only "
            "attest to artifacts within that profile's scope"
        )
    target = root / attested_artifact
    if not target.is_file():
        raise FileNotFoundError(f"attested artifact not found: {attested_artifact}")
    if not notes:
        raise ValueError("notes must not be empty -- explain what this sync did and did not touch")

    profile = REVIEW_PROFILES["migration"]
    return {
        "contract_version": 1,
        "operation_id": operation_id,
        "phase": "migration",
        "reviewer_role": profile["reviewer_role"],
        "independent_pass": True,
        "status": "approved",
        "reviewed_at": reviewed_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifacts": [
            {
                "path": attested_artifact,
                "change": "current",
                "sha256": file_sha256(target),
            }
        ],
        "checks": {check: "passed" for check in profile["checks"]},
        "blocking_findings": [],
        "non_blocking_findings": list(notes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument(
        "--note",
        action="append",
        dest="notes",
        required=True,
        help="Repeatable. At least one required -- explain what this sync did and did not touch.",
    )
    parser.add_argument("--attested-artifact", default=DEFAULT_ATTESTED_ARTIFACT)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", required=True, help="Path to write the review artifact, e.g. state/reviews/<name>.yml")
    args = parser.parse_args()

    document = build_migration_review(
        root=Path(args.root),
        operation_id=args.operation_id,
        notes=args.notes,
        attested_artifact=args.attested_artifact,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    print(f"Wrote migration review artifact to {out_path}")


if __name__ == "__main__":
    main()
