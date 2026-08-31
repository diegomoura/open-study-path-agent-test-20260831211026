# Etapa 11 — integrations off by default

Status: **implemented**. Second half of the post-Etapa-9 handoff's Frente 2
(alongside `docs/claude-agent-pilot-etapa10-remove-slides.md`).

## Why

A new instance should never proactively propose or pre-select an external
task/reminder/scheduling/artifact/analytics tool. Only GitHub Issues (a
required backend, not truly optional) should be active out of the box.
Everything else -- Trello, Todoist, Habitify, Whimsical, Google Drive,
Airtable -- remains real, working, documented capability that activates
only on the learner's explicit request or connection.

## What actually changed

Only the **shipped default values**, not the schema. The schema
(`schemas/study-config.schema.json`) already separates two different
kinds of field per integration category:

- `preferred`/`preferred_external` -- a `const`, purely informational: "if
  this category is ever active, here is the recommended provider." Left
  untouched everywhere; it still documents the richest option (Trello,
  Habitify, Whimsical, Google Drive, Airtable) for someone who opts in.
- `provider`/`external_provider`/`enabled` -- the field that actually
  activates something. `study.config.example.yml` previously shipped most
  of these as `auto`, which resolves to the `preferred` provider unless
  overridden -- i.e., the default instance already leaned toward
  proactively suggesting Trello, Habitify, Whimsical, Google Drive and
  Airtable.

Changed in `study.config.example.yml`:

- `integration_preferences.experience`: `guided_recommendations` ->
  `minimal`.
- `task_manager.provider`: `auto` -> `github_issues` (task_manager has no
  `enabled` field and no `none` option -- some backend is mandatory, so
  the safe default is the one already implemented, not a bare `auto`
  that would otherwise resolve to Trello).
- `habit_tracking`, `visual_workspace`, `artifact_workspace`,
  `analytics_projection`: `provider`/`external_provider` -> `none`,
  `enabled` -> `disabled`.

Deliberately left unchanged:

- `reminders` and `calendar` were already `provider: none` /
  `enabled: disabled` in the template -- not part of the problem.
- `research` (Consensus) and `course_discovery` (Coursera/edX/Udemy/Khan
  Academy) are not account-connected productivity tools the way
  Trello/Notion/Habitify are -- they don't require connecting an
  external account and don't clutter the learner's task/calendar surface
  the same way. Left on `auto`/`enabled` as before.

Intake surfaces updated to match the new default and stop implying Trello
is the recommended choice:

- `.github/ISSUE_TEMPLATE/create-study-path.yml`'s `task_manager` dropdown:
  description rewritten, default option moved from "Deixar o agente
  recomendar" to "GitHub Issues".
- `intake/jotform-form-spec.yml`'s equivalent field: same rewording,
  `default: auto` -> `default: github_issues`.
- `instructions/10-intake.md`'s "internal invariants" line: no longer
  says "Trello preference with GitHub Issues ... as fallbacks"; now says
  GitHub Issues is the default with Trello/Todoist as optional upgrades.
- `docs/integration-capabilities.md`'s "Trello, GitHub Issues, Todoist and
  Markdown" section and `AGENTS.md`'s capability-integration bullet:
  reworded the same way.

No code that implements an integration was touched or removed --
`scripts/integration_resolution.py`, `scripts/github_issues_backend.py`
and every provider-specific validator are unchanged. Only the default
configuration and the intake-facing copy describing that default changed.

## Found, not fixed here (out of scope)

`README.md`'s "Integrações por necessidade" table lists "Flashcards |
Quizlet" as if active, but `docs/integration-capabilities.md`'s "Removed
practice integrations" section says flashcards/Quizlet were removed
entirely. This predates this etapa and is unrelated to the
integrations-off-by-default change -- another instance of the
"reconciliation gap between paired sources of truth" risk category, noted
but not touched here to avoid scope creep.

## Validation

Deterministic only, no API dispatch: `python scripts/validate_template.py
all` (including a `jsonschema.validate()` check of the edited
`study.config.example.yml` against `schemas/study-config.schema.json`),
all 25 `scripts/test_*.py`, and `python -m unittest discover tests/` (46
cases) all pass.
