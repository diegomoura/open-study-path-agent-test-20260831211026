# Track progress

Synchronize activity state from the single authoritative task backend, but mark a topic as mastered only from a verified evaluation produced by `instructions/55-evaluate-topic.md`.

Record timestamps, evidence links, assessment issue references, attempt numbers, scores, mastery decisions and recovery state in `state/progress.json`.

Read `study/integrations.md` and `state/integrations.json` before reading or writing external provider state. Treat external signals according to their authority:

- authoritative task backend: execution state only;
- auxiliary Todoist: reminders only;
- calendar or Reclaim: scheduled and attended sessions only;
- Habitify: consistency only;
- Quizlet or Ace Quiz Maker: formative practice only;
- Drive or another artifact workspace: evidence links only;
- Whimsical: auxiliary visual artifact only;
- Airtable: `github_to_airtable` analytical projection only.

Activity completion is not equivalent to learning. A checked task item, completed reminder, habit streak, elapsed study time, calendar attendance, external course completion or formative score cannot independently mark a topic as mastered.

Update `state/integrations.json` only with safe external identifiers, content versions, authority, synchronization status and timestamps. Reuse resources and avoid duplicates.

When Airtable is selected, project progress only after the canonical GitHub update has been committed. Never read Airtable as the authority for score, mastery or curriculum state.

When an assessment issue exists but has not been evaluated, keep the topic in `Em avaliação` or the equivalent state and provide the normal topic command without requiring the issue number unless lookup is ambiguous:

`Finalizei o TOPIC-000. Avalie minhas respostas.`

When evidence is insufficient or a critical misconception remains, use the focused recovery workflow from `instructions/55-evaluate-topic.md`. Do not unlock dependent topics until mastery rules pass.

An unavailable optional provider uses its documented fallback and does not block tracking. A missing authoritative task connector may defer task synchronization, but canonical progress remains available in GitHub.

## Independent progress review

After preparing a tracking update, run `instructions/04-review-generated-artifacts.md` with the `progress` profile.

The progress reviewer must reconstruct the transition from the previous canonical state, verified assessment attempts and harmless external read-backs. It verifies that:

- every mastery value comes from an approved assessment attempt;
- task, schedule, reminder and habit signals remain auxiliary;
- the transition is allowed and does not skip required states;
- external projections match the canonical result without becoming another authority;
- no duplicate or stale provider resource was introduced;
- the next learner action is derived from the reviewed state.

Store the approved review under `state/reviews/<progress-operation>.yml` and cover each changed progress or integration-state file with its current fingerprint. A provider read-back mismatch is blocking until corrected or accurately recorded as deferred.

Complete each tracking operation using `instructions/phase-completion.md` only after the progress review and generated diff coverage pass. Report only meaningful progress changes, verified evidence, the next available topic or recovery action, and one exact command. Do not dump the entire progress or integration state into chat unless requested.
