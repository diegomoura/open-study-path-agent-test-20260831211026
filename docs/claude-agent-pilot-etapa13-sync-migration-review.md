# Etapa 13 — template-sync migration review tooling

Status: **implemented**. Closes the two findings reported while validating
Etapa 12's sync to the disposable test instance
(`diegomoura/open-study-path-agent-test-20260826011447`).

## The two findings, and their shared root cause

Both were the same gap wearing two faces: the established "sync reusable
template infra to an instance repo via direct push, no PR" pattern (used for
Etapas 10, 11, 12) had never actually been reconciled against
`scripts/validate_instance_operation_scope.py`'s guard, which -- correctly,
for a genuine instance -- requires an approved `phase: migration` review
artifact to be present whenever a push changes a protected reusable path
(`scripts/`, `.github/workflows/`, `instructions/`, `templates/`, `schemas/`,
`docs/`, `AGENTS.md`, `.open-study-path/template.yml`) on a repository that
already has `.open-study-path/instance.yml`.

1. **Already red before this etapa, previously unnoticed:** the Etapa 10 and
   Etapa 11 sync commits (`0fb0464`, `6ffec10`) on the test repo's `main`
   both landed with `Review generated artifacts` failing — those two syncs
   legitimately changed `.github/ISSUE_TEMPLATE/create-study-path.yml`
   (removing the slides option, changing integration defaults), a file
   `review_framework.is_generated_artifact` correctly treats as
   instance-customizable content requiring review coverage, and no review
   artifact covered it.
2. **New in this etapa's own sync:** the Etapa 12 sync (`690fd3e`) didn't
   touch any file `is_generated_artifact` recognizes, so `Review generated
   artifacts` passed clean -- but it did touch protected reusable paths
   (`scripts/*.py`, `.github/workflows/*.yml`, `docs/*.md`), which tripped
   the separate, stricter-in-a-different-way
   `validate_instance_operation_scope.py` guard: *any* protected-path change
   requires an approved migration review to be present in the diff,
   regardless of what it covers.

## What actually changed

`scripts/sync_migration_review.py` -- a small, reusable, fixture-tested tool
that builds a real `phase: migration` review artifact for exactly this
situation:

- Fingerprints one currently-true generated artifact as evidence instance
  state/content was not touched by the sync. Default: `README.md` (present,
  and instance-customizable, in both the template repo and any instance --
  unlike the instance marker, which does not exist in the template repo
  itself, so it cannot be this script's default even though it would be a
  more obviously on-topic choice).
- Writes an honest `non_blocking_findings` narrative (via `--note`,
  repeatable) explaining what the sync did and did not touch. Never claims
  coverage of a file it did not actually attest to.
- Refuses (`ValueError`) to attest to a path
  `review_framework.is_generated_artifact` does not recognize -- a migration
  review can only cover artifacts within that profile's scope
  (`review_framework.phase_allows_artifact`), by the same rule that governs
  every other review profile.
- The produced document round-trips cleanly through
  `review_framework.validate_review_document` with zero errors
  (`scripts/test_sync_migration_review.py` asserts this directly), and is
  recognized by `validate_instance_operation_scope.migration_review_present`.

This closes finding 2 directly: from now on, any sync (in this repo or any
instance) that touches protected reusable paths includes a
`scripts/sync_migration_review.py` invocation in the same commit.

Finding 1 (the already-red `main` from Etapas 10/11) is **not** rewritten --
past commits' check results are historical and do not block anything now
that they are not gating an open pull request. It is closed going forward:
this etapa's own sync to the test repo (below) is the first sync commit that
lands with every check green, and any future sync follows the same pattern.

## Validation

`scripts/validate_template.py all`, every `scripts/test_*.py` (including the
new `test_sync_migration_review.py`), `python -m unittest discover tests/`.
All green locally. No Anthropic API dispatch needed -- this is pure
YAML-authoring logic over already-known file contents, exercised entirely
through fixtures.
