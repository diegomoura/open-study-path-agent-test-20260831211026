# Recover intake completion without a learner dead end

Apply this contract during the `intake` phase after the normalized artifacts and intake review have been authored.

## Complete the review profile before the first push

Build the review from `scripts/review_framework.py`, not from memory or a partial example. The intake review must contain every required check with `passed`, including:

- `request_fidelity`;
- `preference_preservation`;
- `ambiguity_resolution`;
- `data_minimization`;
- `next_phase_consistency`.

Before opening or updating the pull request, validate the review locally when execution is available. Missing required keys, stale fingerprints and incomplete generated-artifact coverage are deterministic authoring defects and must be repaired in the same pull request.

## Repair deterministic CI failures

When CI reports a missing required review check, stale fingerprint, incomplete coverage, schema mismatch or another deterministic defect:

1. read the failing job for the current pull-request head;
2. repair every finding of the same class in one batch;
3. keep the same operation ID, branch and pull request;
4. refresh review fingerprints after the final artifact changes;
5. rerun validation;
6. merge under `workflow.intake_merge_policy` when the corrected head is green and no material decision remains.

Do not ask the learner to inspect CI, edit YAML, refresh hashes or restart the intake.

## CI in progress is not completion

A response that says only that validation is still running does not complete the operation and does not continue by itself. Do not offer a passive wait as completion.

Use a small bounded number of status reads during the active turn. When checks finish within that bound, handle the terminal result immediately:

- success: merge and continue to the diagnostic when authorized;
- deterministic failure: repair in the same pull request and validate again;
- material decision: ask only for that decision;
- infrastructure failure that cannot be repaired: report the precise blocker.

When checks remain queued or running after the bounded observation, state truthfully that the operation is not complete. Do not imply background work unless an actual monitor was created. The learner-facing response must not claim that the diagnostic will start automatically later.

## Regression case

The canonical regression is an intake review that contains the four normalization checks but omits `next_phase_consistency`. Validation must reject it; adding `next_phase_consistency: passed` to the same review must make the review valid without changing the learner's imported data.
