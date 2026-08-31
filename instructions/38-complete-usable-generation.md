# Complete the usable learning window

Apply this contract during initial curriculum generation and every rolling-window materialization.

Pedagogical readiness is the single completion dimension: lesson, practice, assessment, flashcards, content review and curriculum review are current.

## Durable states

For every materialized topic, persist this state in the active operation record:

- `lesson_ready`: `pending | ready | failed`.

Persist the checkpoint `learning_window_usable` as soon as every eligible topic in the active window has `lesson_ready: ready`. Record its timestamp and the exact topic IDs.

## Required order

1. Generate all pedagogical artifacts for the active window.
2. Run content and curriculum review.
3. Refresh every affected generated-artifact fingerprint in one deterministic batch.
4. Run the fast pedagogical validation without installing Playwright or Chromium.
5. Persist `learning_window_usable` when it passes.
6. Publish external task resources only according to the selected backend's required resource policy.

Do not create one commit per repaired fingerprint. Do not stop after reporting a known deterministic mismatch. Repair all mismatches of the same class before the next push.

## Learner-facing response

When `learning_window_usable` exists, never reply only that creation is incomplete.

Report:

- which lessons are already usable;
- whether external publication is complete or still pending;
- the exact blocking stage when one remains.

## Timing

Record stage timestamps and durations for at least:

- pedagogical generation;
- review refresh;
- pedagogical validation;
- `learning_window_usable`;
- external publication.
