# Configure intake

Run this phase only in an Open Study Path instance. It prepares the selected intake method but does not import responses or generate a curriculum.

Read and apply `instructions/02-setup-execution.md`. Intake configuration is part of the same first-chat setup operation and uses the same allowed diff and merge gate.

## Provider selection

When no provider is configured, let the owner choose:

1. `github_issue` — recommended because the form already exists in the repository;
2. `jotform` — create a form in the connected account;
3. `manual_yaml` — edit `study.config.yml` directly.

Do not silently select Jotform or create external resources without the owner's choice.

## GitHub Issue Form

1. Confirm `.github/ISSUE_TEMPLATE/create-study-path.yml` exists in the target repository. Do not infer absence from repository size or search metadata.
2. Read the exact repository identity from `.open-study-path/instance.yml`.
3. Confirm the form file contains the current hidden identity marker exactly once:

   `<!-- open-study-path:intake form_id=create-study-path version=4 -->`

   The marker identifies the checked-in form contract. It lives inside a form `markdown` block and is not expected to appear in the body of a submitted issue.
4. Confirm the form does not prefill the native issue title and that its first visible instructions explain: use **Add a title** for the course name. GitHub requires that title before submission; the form must not ask for the name a second time.
5. Verify repository labels `study-request` and `intake:imported` exist. Create only missing labels through the GitHub labels API or run **Ensure repository labels**, which invokes `scripts/ensure_repository_labels.py`. Read the labels again after provisioning.
6. Configure the inherited GitHub Issue Form with these exact metadata values:

   ```yaml
   created_by: reused_existing
   submission_strategy: unique_verified_candidate
   ```

   `reused_existing` records that setup reused the form inherited from the template; it does not claim that the instance owner created it during setup. `unique_verified_candidate` records the actual import rule: automatically import only when exactly one current, unimported and contract-valid rendered issue remains after deterministic filtering. Never select the newest issue merely because it is newest. An explicitly supplied issue number may narrow a later lookup, but `explicit_issue` is not the default persisted strategy for this form.
7. Mark the GitHub Issue Form as ready only after the form marker, title guidance, both labels and the metadata above are verified.
8. Build the direct URL:

   `https://github.com/OWNER/REPOSITORY/issues/new?template=create-study-path.yml`

9. Return it as a direct clickable link with a human label such as **Preencher meu formulário**.
10. Stop after setup and use the natural command:

   `Preenchi o formulário. Pode continuar.`

The form is inherited reusable infrastructure. Do not edit, recreate or replace it during normal instance setup. Configure only the instance marker and `study.config.yml` unless a verified template defect requires a separate canonical-template fix.

Do not mark setup or intake ready when label existence, title guidance or the current form marker cannot be verified. Do not create or submit an issue, import answers, run the diagnostic or generate curriculum during setup. Do not require an issue number.

Only the current repository form contract is supported. The submitted issue is later identified from its automatic `study-request` label, expected rendered headings, required responses, checked consent, title and import state. Do not expect the form marker in the issue body and never ask the learner to add it manually. An explicit issue number may narrow deterministic lookup when the owner supplies it or when multiple valid candidates require disambiguation, but it never bypasses those submission checks.

## Jotform

Confirm the app is connected before reading or creating a form. Never request or store an API key.

Reuse an existing exact form for this instance when verified. Otherwise create it from `intake/jotform-form-spec.yml` in the owner's selected workspace. Do not create a test submission.

Persist only safe metadata: provider, setup status, form ID and URL, specification ID/version, creation mode, attachment policy and `persist_raw_submission: false`.

Return the form link and:

`Preenchi o formulário. Pode continuar.`

Stop before reading submissions.

## Manual YAML

Set the manual provider and return the configuration path. Required facts are course name, the complete learning request, a concise subject, current level and preferred language. Do not invent them. Objective details, time constraints, learning preferences and integration choices remain optional.

Use:

`Preenchi minha configuração. Pode continuar.`

## Instance marker

Update setup and intake-provider status in `.open-study-path/instance.yml`. Setup complete means only that the instance and intake method are ready.

If `bootstrap_instance` already ran on this repository, every status field this phase would set may already be correct (this is the expected outcome for the `github_issue` provider, which needs no further configuration). Do not write a file just to have something to write. Verify each requirement above yourself, and if every one is already met, call `finish_phase` with `no_changes_needed=true` and a `reason` naming exactly which checks you verified and how -- an independent reviewer still re-checks the repository directly against this same contract before anything is accepted, so this is not a shortcut around review, only around writing a no-op diff.

Validate the complete setup diff and required checks for the current head. Do not merge or report successful configuration while a required check is failing, pending, cancelled, missing or unreadable.

Complete with `instructions/phase-completion.md`. Return the selected form or configuration path and make the next human action unmistakable.

<!-- Contract markers: direct clickable link; unique_verified_candidate; explicit_issue; explicit issue number remains accepted; Do not require the owner to copy an issue number; current repository form contract; submitted issue does not contain the form marker; never ask the learner to edit technical markers. -->
