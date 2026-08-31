# Evaluate a completed topic

Evaluate a materialized topic from an explicit topic ID. The assessment issue number is optional when the correct submission can be resolved deterministically.

The standard command is:

`Finalizei o TOPIC-000. Avalie minhas respostas.`

The explicit fallback remains supported:

`Finalizei o TOPIC-000. Avalie a issue #<número>.`

## Resolve the assessment issue

When an issue number is provided, read it and validate that it matches the requested topic.

When no issue number is provided, search the instance repository for candidate issues using these authoritative signals:

1. label `assessment`;
2. label `assessment:submitted`;
3. body containing `open-study-path:assessment topic_id=TOPIC-000`;
4. not already recorded as an evaluated attempt under `state/assessments/TOPIC-000/`;
5. not labeled `assessment:graded`;
6. created after the last recorded attempt when an earlier attempt exists.

A title beginning with `[Avaliação] TOPIC-000` is a preferred consistency signal, but it is not mandatory when the hidden topic marker and labels uniquely identify the submission. GitHub Issue Form titles remain editable by the learner.

Use the issue author as an additional filter when the learner identity is known from the active authenticated context. Do not persist unnecessary identity data solely for this lookup.

- Exactly one valid candidate: evaluate it automatically.
- No candidate: state that no submitted assessment was found and provide the direct topic form link.
- More than one candidate: show only the candidate issue numbers and links and ask which one should be evaluated.

Never choose an arbitrary newest repository issue.

After resolving exactly one candidate, normalize its title to `[Avaliação] TOPIC-000 — <topic title>` when it differs. This is repository hygiene, not an assessment criterion. Never reject or penalize an otherwise valid submission because the learner edited the title.

## Required inputs

Before scoring:

1. read the approved topic contract;
2. confirm `content_status: materialized`;
3. read the complete module;
4. read the scoring rubric;
5. read the full resolved assessment issue;
6. read existing topic attempts when present.

External task, reminder, calendar, habit, flashcard, visual, artifact or analytics data may provide context, but it is never a substitute for the durable assessment submission. Do not require an optional provider to be available before grading.

If answers are incomplete, the issue belongs to another topic or deterministic resolution is ambiguous, do not grade.

## Response-by-response grading

Grade every response independently against the matching rubric item. For each question, provide:

- points earned and maximum points;
- what the response demonstrated correctly;
- the exact gap, misconception or missing reasoning;
- one actionable improvement suggestion.

Calculate a total score from 0 to 100. A topic is mastered only when:

- the score meets or exceeds `passing_score`;
- no critical misconception remains;
- required deliverable or evidence is present and usable.

Checklist completion, time spent, task state, Todoist reminders, Habitify streaks, calendar attendance, external-course completion or a formative quiz/flashcard score is not sufficient mastery evidence by itself.

## Persist and label the proposed result

Prepare the detailed evaluation comment and create the next versioned result under:

`state/assessments/TOPIC-000/attempt-001.json`

Record topic ID, issue number and URL, attempt, timestamp, per-question score and feedback, total, mastery, critical misconceptions, recovery actions and evaluator method.

Prepare the matching `state/progress.json` transition. GitHub is the only authority allowed to persist `mastered: true`.

Do not publish the comment, final labels, external projections or a mastery completion response until the independent assessment review has approved the proposed score and state transition.

## Independent assessment review

After the grading pass, run `instructions/04-review-generated-artifacts.md` with the `assessment` profile as a separate reviewer role.

The assessment reviewer must re-read the submission and rubric and independently recompute:

- the candidate issue resolution;
- the score for every response;
- the total score;
- every critical misconception decision;
- whether the evidence satisfies the deliverable;
- mastery or recovery status;
- the progress transition;
- the next materialization and learner action.

The reviewer must not copy the original evaluator's score and merely check arithmetic. It must compare the reasoning with each rubric criterion and record any disagreement as a blocking finding until corrected.

When successful evaluation automatically materializes new topics, the assessment review covers those generated artifacts too and confirms that every new materialized topic has its specialized current content review.

Store the approved operation review under `state/reviews/<assessment-operation>.yml`, with current fingerprints for every generated attempt, progress, curriculum, integration and assessment artifact changed by the operation.

## Finalize repository and issue state

Only after the independent assessment review and CI pass:

- post the approved detailed evaluation as a comment on the assessment issue;
- persist the reviewed attempt and progress files;
- remove `assessment:submitted` from the issue;
- add `assessment:graded` when mastered;
- add `assessment:recovery-required` when recovery is required.

If the connector write-back occurs after the repository merge, read the issue back and persist or reconcile the safe external result in the operation state before declaring completion.

## Synchronize derived providers

After the GitHub result is persisted, use `study/integrations.md`, `study.config.yml` and `state/integrations.json` to synchronize only derived representations.

- Move or complete the authoritative task backend according to the GitHub result.
- Auxiliary Todoist reminders may be completed or archived, but never determine the result.
- Habitify may record a study or review habit, but not mastery.
- Calendar resources may be updated or canceled based on the next plan.
- Quizlet or Ace results remain formative and need no score import into mastery.
- Airtable may receive the new attempt and progress as a `github_to_airtable` projection only.
- External visual or artifact workspaces receive links or status metadata only when relevant.

Run harmless provider probes before writes. An unavailable optional provider records a deferred or fallback sync and must not undo or block the GitHub evaluation.

## When the topic is mastered

1. complete or move the authoritative task to `Concluído`;
2. unlock eligible dependent topics;
3. automatically execute `instructions/57-materialize-next-content.md` to restore the configured content window;
4. run the specialized content reviewer for every newly materialized topic;
5. update newly materialized external resources after capability-based probes;
6. project the verified result to Airtable only when selected and available;
7. include all resulting generated artifacts in the assessment operation review;
8. return the next ready materialized topic with module, authoritative task and form links.

The learner must not send a separate command to generate the next topic.

## Recovery and focused reassessment

When the topic is not mastered:

1. identify only failed rubric dimensions and critical misconceptions;
2. create a focused GitHub recovery issue with targeted study tasks and a reassessment covering only weak areas;
3. create or update `RECOVERY-TOPIC-000-A<attempt>` in the authoritative task backend;
4. link the recovery issue, original assessment, module and topic task;
5. create optional reminder, schedule, habit or flashcard recovery support only when selected and available;
6. keep the topic out of `Concluído`;
7. require a new evidence attempt.

The standard recovery command is:

`Finalizei a recuperação do TOPIC-000. Avalie minhas respostas.`

Resolve the recovery issue deterministically using its topic, attempt marker and unresolved recovery status. Request an issue number only when more than one valid recovery submission remains.

Do not repeat mastered questions unless necessary to confirm correction of a critical misconception.

## Optional formative practice

Quizlet, Ace Quiz Maker, local Markdown flashcards, importable TSV files and chat-generated quizzes may supplement practice. They never replace the durable GitHub assessment, rubric, evidence and response-by-response evaluation.

## Completion response

Report the score, mastery decision, resolved assessment issue and either the focused recovery path or the next ready materialized topic. Include any automatic materialization PR as an artifact. Briefly report optional integration fallbacks or deferred syncs, but do not require another command before study continues.
