# Await CI and finish the operation

Use this internal contract whenever the resolved merge policy is `auto_when_unambiguous` or `agent_review_then_merge`. Execute the state transitions defined by `scripts/ci_completion_state.py`; do not improvise another order.

## Resolve the completion contract

Read `instructions/manifest.yml` and resolve:

1. the current phase and suboperation;
2. the operation check sets declared for it;
3. the exact workflow names in those check sets;
4. the repository-required status checks from branch protection, when that API is available;
5. the union of repository-required checks and operation-required checks.

The manifest is authoritative for operation-specific checks. Branch protection adds requirements but never removes manifest requirements. Do not infer required checks merely from whichever workflows happened to start. A missing expected check is a blocker.

## Required transition order

After the final review and deterministic repair:

1. Push one final head and capture it as `expected_head_sha`.
2. Confirm there is no explicit no-merge request and no unresolved material decision.
3. Mark the pull request ready for review. A draft pull request cannot be merged or configured for auto-merge.
4. Detect whether the repository supports auto-merge.
5. If supported, enable auto-merge only after the ready transition succeeds.
6. Observe every required check for exactly `expected_head_sha`.
7. If the head changes at any point, discard all prior observations and restart from step 1 with the new head.
8. When every required check succeeds, merge using `expected_head_sha` as the atomic precondition. Even when auto-merge was enabled, re-read the pull request; if it has not merged yet and the connector permits an atomic manual merge, merge the exact validated head.
9. Read the default branch and verify the persisted lifecycle state and expected artifacts before presenting the next command.

Never merge without an expected-head precondition. If the merge is rejected because the head moved, restart validation instead of retrying blindly.

## Executable state machine

Build a fresh `CompletionContext` and apply `decide_next_action` from `scripts/ci_completion_state.py` after every GitHub read or mutation. Execute exactly one returned action, then rebuild the context from fresh data.

The state machine can return:

- `mark_ready`;
- `enable_auto_merge`;
- `wait`;
- `retry_transient`;
- `repair_deterministic_failure`;
- `merge_expected_head`;
- `verify_default_branch`;
- `complete`;
- an explicit blocking state.

A successful `merge_expected_head` action must pass its returned `expected_head_sha` to the GitHub merge operation. `complete` is valid only after the default branch contains the expected persisted state, not merely because the pull request is closed.

## Bounded polling

Do not use one long fixed sleep. Poll with bounded backoff: 10, 15, 20, 30 and then 45 seconds. Re-read the pull-request head before every status query.

When workflow timestamps are available, calculate the observation budget in memory with `estimate_wait_budget_seconds`:

- use at most the 5 most recent successful durations for the same required workflows;
- use the larger of twice the median or 1.25 times p90;
- minimum budget: 3 minutes;
- maximum budget: 15 minutes;
- default without samples: 10 minutes.

Do not commit timing metrics, update a state artifact or push another head merely to record wait estimates. Timing data is advisory, ephemeral and must never override current GitHub status. Do not store logs, tokens, runner identifiers or learner data.

## Check interpretation

Only observations attached to `expected_head_sha` count.

- `success`: continue toward atomic merge.
- `failure`: inspect the failing step; repair a deterministic finding on the same branch, create a new head and restart the full observation window.
- `cancelled` or `timed_out`: retry once when clearly transient. A second transient failure is an infrastructure blocker.
- `queued` or `in_progress`: wait within the bounded budget.
- missing required check: block; never treat absence as success.
- `skipped`, `neutral`, `action_required` or any unknown non-success conclusion: block unless the operation contract explicitly declares it acceptable.
- merge conflict: block and report the concrete repository problem.

A run cancelled by `concurrency` because a newer head exists must not satisfy the older head. Restart observation for the current head.

## Budget exhaustion

When the observation budget is exhausted, do not claim that work will continue invisibly. If auto-merge was successfully enabled, state only that the operation is still incomplete and do not provide the next lifecycle command. If auto-merge is unavailable, report the infrastructure blocker and exact PR only when owner intervention is genuinely required.

## Learner-facing rule

Pending CI is not a successful learner-facing terminal state. Never end with language such as `a validação ainda está em execução` while the agent can continue observing. Do not provide the next lifecycle command until `complete` is reached and the merged state is confirmed on the default branch.
