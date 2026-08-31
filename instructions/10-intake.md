# Import intake

Run this phase only in instance mode after intake setup is ready. Use only the configured form or approved manual configuration belonging to the instance.

The natural command `Preenchi o formulário. Pode continuar.` approves importing the single valid unimported submission found by deterministic filtering. It never authorizes choosing an arbitrary newest submission.

## Jotform

- Fetch the configured form and confirm access.
- Find submissions containing all required planning facts and not already recorded in `state/intake-summary.json.source_reference`.
- Use an explicitly supplied submission ID when verified.
- Import automatically when exactly one valid candidate remains.
- When none remain, return the form link.
- When several remain, list only the concise information needed for the owner to choose.
- Do not combine submissions, select the newest silently or persist raw submissions and uploads.

## GitHub Issue Form

Search only the instance repository. Apply the algorithm in `scripts/intake_resolution.py`; do not replace it with similarity or newest-issue heuristics. That algorithm matches headings by exact, line-anchored string comparison, not semantically: build each heading you pass to `resolve_intake_candidates` as `### ` followed by the field's exact `label:` text from `.github/ISSUE_TEMPLATE/create-study-path.yml`, verbatim (same wording, accents and punctuation, no trailing colon). A real dispatch produced a rejection with every required field and consent simultaneously reported missing against a submission that read as complete and correctly filled -- the cause was headings built without the `### ` prefix, not a bad submission; because every field is built the same way, one formatting slip fails all of them at once and looks identical to a genuinely malformed issue. If a submission that reads as complete gets rejected, re-derive the heading strings character-for-character from the form YAML before concluding the submission itself is the problem.

### Form contract and submission identity

The supported form version comes from the checked-in repository contract, not from a hidden comment in the rendered issue:

- `.github/ISSUE_TEMPLATE/create-study-path.yml` must contain exactly one current form marker: `<!-- open-study-path:intake form_id=create-study-path version=4 -->`;
- `study.config.yml` and `intake/field-mapping.yml` must identify the same current form specification and version;
- the marker belongs to a form `markdown` block used for repository validation; GitHub does not include that block in the submitted issue body.

Never require, search for or repair this marker in a learner's issue body. Never ask the learner to edit an issue to insert a technical marker. A manually inserted marker is not proof of form origin and does not replace any submission check.

A valid rendered issue candidate must satisfy all of these identity and state checks:

- it is an issue, not a pull request;
- it has the `study-request` label configured by the current Issue Form;
- its body contains the expected field headings from `.github/ISSUE_TEMPLATE/create-study-path.yml`;
- every currently required form field has a non-empty rendered response;
- the consent section contains its required checked checkbox;
- its issue title contains a non-empty course name;
- when the expected instance owner or approved submitter is known, its author matches that allowed identity;
- it is not already identified by `state/intake-summary.json.source_reference`;
- it does not have the `intake:imported` label.

Treat the trimmed issue title as the synthetic field `issue_title` and map it to `path.name` through `intake/field-mapping.yml`. Preserve the learner's title as the course name. Do not add a prefix or generic suffix. Do not rewrite the issue title during import.

The `study-request` label is part of submission identity and must already be present. Do not add it to an arbitrary issue to make that issue importable. Missing repository label definitions are repaired during setup, not during candidate classification.

Only the current repository form contract is supported. Reject missing expected headings, missing required responses, unchecked consent, missing discovery label, unexpected author when author constraints are known, empty title or imported state. Matching headings alone, a unique recent issue or similar answers never establish identity. An explicit issue number narrows the search but does not bypass label, structure, required-response, consent, author, title or import-state checks.

### Selection and import

When the form was reported as submitted:

1. verify the current form marker and version in the repository form and configuration;
2. classify rendered issues using label, structure, required responses, consent, author when known, title and import-state rules;
3. import automatically when exactly one valid candidate remains;
4. when none remain, return the direct form link only when there truly is no matching submission;
5. when a candidate exists but a repository contract inconsistency prevents verification, report the internal blocker and correct the template or instance contract; do not ask the learner to add technical metadata to the issue;
6. when more than one remains, list candidate number, title and creation time and ask the owner to choose;
7. never select an arbitrary newest repository issue.

After import, persist the exact source reference, apply `intake:imported` and retain `study-request` for auditability. Treat attachments as optional and do not copy them into the repository by default. The source reference and every other import-audit fact (issue number, title, timestamp) belong only in `state/intake-summary.json.source_reference` -- `study.config.yml`'s `intake:` block is a closed schema (`additionalProperties: false`) describing the provider's setup, not the specific submission, and does not accept audit fields. A real dispatch added `imported_from_issue`/`imported_at` there and failed CI's schema validation for exactly this reason.

## Manual YAML

Read only learner-approved values in `study.config.yml`. Do not interpret placeholders as confirmed facts.

## Planning facts

Required facts are course name, complete learning request, concise subject, current level and preferred language. Objective details, desired outcome, motivation, time constraints, accessibility, references, learning preferences and integration answers are optional.

Preserve the complete answer to “O que você quer aprender?” in `path.learning_request`. Derive `path.subject` as a short factual topic label of at most 120 characters. Do not replace the original answer with the summary and do not add scope that the learner did not request.

Normalize approved answers through the provider-specific mappings in `intake/field-mapping.yml` into `study.config.yml` and `state/intake-summary.json`. Normalize language to `pt-BR` or `en`. Missing optional answers must not block the course. Record only necessary conservative assumptions.

A value in `path.time_constraints` is planning context, not permission to remove mastery-required content or claim that an unrealistic course fits the available time. Preserve the complete dependency-aware course, identify a sensible priority order when useful and explain feasibility honestly. Create a dated or weekly projection only after an explicit request and the minimum scheduling details are known.

Do not recommend, connect or probe external tools during intake. Keep delegated provider choices as `auto` until diagnostic and curriculum context exist. An empty learning-format selection delegates the choice to the course generator. The theory/practice balance defaults to `balanced`.

When the learner chooses not to connect other accounts, normalize `integration_preferences.account_connections: no_external_accounts`. Do not later suggest, probe or write to providers that require another account; use GitHub Issues or the repository-native Markdown fallback. Otherwise use `ask_per_provider`, preserving explicit tool constraints in `integration_preferences.notes`.

Internal invariants such as GitHub authority, formative-practice limits, Mermaid canonical status, GitHub Issues as the default task backend with Trello and Todoist as optional upgrades and Markdown as the final fallback, one primary task backend and `github_to_airtable` analytics are normalized without requiring the learner to repeat them. Do not surface those terms in the success response.

Update `.open-study-path/instance.yml` with completed intake status.

## Pull request and merge

Create a PR limited to the instance marker, `study.config.yml`, `state/intake-summary.json` and one intake review artifact under `state/reviews/`. Apply `workflow.intake_merge_policy`.

After authoring, run `instructions/04-review-generated-artifacts.md` with the `intake` profile. The reviewer must compare the selected source with every normalized learner fact, integration preference, assumption and consent decision. It must also verify that `path.learning_request` preserves the original answer, `path.subject` is only a concise label and time constraints were not converted into silent scope loss. Auto-merge only when facts, validation, privacy, scope, assumptions and generated diff coverage are unambiguous.

Technical review belongs in GitHub. In chat, do not report changed files, CI or merge details after success unless requested or needed to explain a blocker.

## Diagnostic continuation

Do not begin diagnostic until import, independent intake review, validation and required merge complete.

When the command authorizes continuing, immediately run `instructions/20-diagnostic.md`, state the small question range and ask the first question.

When import only was requested, use:

`Vamos fazer meu diagnóstico.`

The explicit chained command remains accepted:

`Inicie o diagnóstico proporcional desta trilha. Faça perguntas curtas, uma por vez. Não gere a trilha ainda.`

If no unique candidate exists or a real decision is required, stop and surface only the action that resolves it.

<!-- Contract markers: expected field headings; exactly one valid candidate; When none remain; more than one remains; state/intake-summary.json.source_reference; intake:imported; immediately invoke `instructions/20-diagnostic.md`; auto_when_unambiguous; rendered Issue Form; required checked consent; technical marker belongs to the repository form; never ask the learner to edit a marker. -->
