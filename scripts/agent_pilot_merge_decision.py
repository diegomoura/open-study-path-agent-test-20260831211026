#!/usr/bin/env python3
"""Pure auto-merge decision for the agent-pilot workflow (Opcao C).

Does not call GitHub. Takes an already-parsed review artifact document (see
``templates/review.yml`` / ``scripts/review_framework.py``) plus a mapping of
GitHub Actions job results (job id -> "success" | "failure" | "cancelled" |
"skipped" | ...), and returns one explicit decision: merge, or block with
concrete reasons.

Design (see the handoff this implements, "Opcao C"):

- Merge automatically only when the reviewer's independent-review artifact is
  genuinely approved (reusing ``review_framework.validate_review_document``,
  the same fingerprint/coverage validation the human-facing pipeline already
  requires -- not just a raw ``status == "approved"`` string match) AND every
  required completion-check job (``scripts/resolve_completion_check_sets.py``)
  succeeded.
- Any other outcome blocks: the pull request is left open exactly as it is
  today, for a human to decide.
- A job result of "skipped" only satisfies a required check if that job was
  never required in the first place (the workflow's own `if:` conditions
  already encode that); if a job id this module was told is *required*
  reports anything other than "success" -- including "skipped" -- that is a
  block, never a silent pass. A required check skipping (e.g. a workflow_call
  step never ran because of an infrastructure problem) must never be
  mistaken for that check having passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from review_framework import validate_review_document

SUCCESS = "success"


@dataclass(frozen=True)
class MergeDecision:
    should_merge: bool
    reasons: tuple[str, ...]


def decide_merge(
    *,
    root: Path,
    review_relative_path: str,
    base_sha: str | None,
    required_job_ids: frozenset[str],
    job_results: dict[str, str],
) -> MergeDecision:
    reasons: list[str] = []

    validation = validate_review_document(root, review_relative_path, base_sha=base_sha)
    reasons.extend(validation.errors)

    for job_id in sorted(required_job_ids):
        result = job_results.get(job_id)
        if result != SUCCESS:
            reasons.append(
                f"required check {job_id!r} did not succeed (result={result!r})"
            )

    unexpected_jobs = set(job_results) - required_job_ids
    # Jobs outside required_job_ids are not inspected -- the caller (the
    # workflow's resolve-checks job) already decided which ones are required
    # for this phase; an optional job's own result is irrelevant here.
    del unexpected_jobs

    return MergeDecision(should_merge=not reasons, reasons=tuple(reasons))


def main() -> None:
    import argparse
    import json

    from resolve_completion_check_sets import load_manifest
    from resolve_completion_check_sets import required_job_ids as resolve_required_job_ids

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--review-artifact", required=True, help="Path to state/reviews/agent-pilot-<phase>.yml")
    parser.add_argument("--base-sha", default=None)
    parser.add_argument(
        "--job-results-json",
        required=True,
        help='JSON object mapping job id to GitHub Actions job result, e.g. {"ci-intake": "success"}',
    )
    parser.add_argument("--manifest", default="instructions/manifest.yml")
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    required = frozenset(resolve_required_job_ids(manifest, args.phase))
    job_results: dict[str, str] = json.loads(args.job_results_json)

    decision = decide_merge(
        root=Path("."),
        review_relative_path=args.review_artifact,
        base_sha=args.base_sha or None,
        required_job_ids=required,
        job_results=job_results,
    )

    print(f"should_merge={'true' if decision.should_merge else 'false'}")
    for reason in decision.reasons:
        print(f"reason={reason}")


if __name__ == "__main__":
    main()
