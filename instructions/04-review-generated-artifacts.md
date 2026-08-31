# Review every generated operation

Run this instruction after the authoring pass of every lifecycle or migration operation and before final validation, merge or success response.

This shared contract does not replace specialized review. Materialized lessons still require `instructions/36-review-course-content.md`; integrations still require their resolution and projection checks; this pass verifies the whole operation and records evidence that CI can enforce.

## 1. Resolve the review profile

Read `instructions/manifest.yml`. Use the phase's `review_profile`:

- setup;
- intake;
- diagnostic;
- curriculum;
- publication;
- assessment;
- progress;
- replan.

Use `migration` for repository synchronization or migration work outside the normal lifecycle.

Read `docs/review-framework.md` and the profile definition in `scripts/review_framework.py`.

## 2. Separate authoring from review

Finish the authoring pass first. Then start a distinct review pass as the profile's reviewer role.

During review:

- re-read the approved inputs and current repository output;
- do not rely on the author's rationale or success claim;
- inspect the complete generated diff;
- read external resources back through harmless operations when available;
- actively search for contradictions, omissions, stale state, false success and an incorrect next action;
- run specialized reviewers required by the operation;
- classify findings as blocking or non-blocking.

The same runtime may perform both passes, but it must change responsibility, reconstruct evidence from artifacts and record `independent_pass: true` only after the separate review occurred.

## 3. Review by profile

### Setup

Check repository identity, preservation of inherited reusable assets, intake form readiness, labels and markers, absence of secrets, and the next setup action.

### Intake

Compare the structured result with the selected intake submission. Check goals, level, language, time, accessibility, tool preferences, consent, unresolved ambiguity and data minimization. A preference may not disappear or be invented.

### Diagnostic

Check that every placement conclusion is supported by the bounded responses, that professional experience in another area was not treated as subject mastery, that the question budget was respected, and that no raw transcript or unnecessary personal data was persisted.

### Curriculum

Check the complete course architecture against intake and diagnostic evidence. Verify scope, graph, prerequisites, effort, level, learner language, integration plan and assessment design. Confirm every materialized topic has an approved current specialized content review and that cross-topic promises remain coherent.

### Publication

Compare the approved plan, configuration, durable state and external read-backs. Verify every explicit selection has a terminal disposition, task content matches its topic, links and versions are current, writes are idempotent, optional tools do not gain authority, and the next action is derived from persisted state.

### Assessment

Resolve the exact submission deterministically. Re-score independently against the rubric instead of trusting the authoring score. Check feedback, critical misconceptions, evidence handling, persisted attempt, progress transition, recovery or mastery decision, and any automatically materialized content.

### Progress

Check that repository and external execution state agree without creating a second mastery authority. Validate allowed transitions, completion evidence, task movement and the single next learner action.

### Replan

Require explicit evidence for the change. Preserve the approved goal unless the learner changed it, revalidate dependencies and effort, refresh affected versions and reviews, and explain learner-visible impact without silently rewriting completed history.

### Migration

Verify exact source and target identities, compatibility rules, state and history preservation, idempotent reruns, duplicate prevention, failure recovery and safe rollback. Never declare migration successful from file counts alone.

## 4. Correct before approval

Correct every resolvable blocking finding on the operation branch. Re-run specialized and deterministic checks after correction.

When a blocking finding requires a real human decision, keep the review `action_required`, do not merge and ask only for that decision.

Do not downgrade a material contradiction to non-blocking merely to complete the phase.

## 5. Record exact review evidence

Create or update one YAML artifact under:

`state/reviews/<operation-id>.yml`

Use `templates/review.yml`.

The review must include every generated artifact changed by the operation. For a current or added file, record `change: current` and its lowercase SHA-256 digest. For a reviewed deletion, record `change: deleted` and `previous_sha256` from the exact pull-request base. A generated path omitted from all approved review artifacts in the pull request blocks CI.

Use a stable lowercase operation ID, for example:

- `setup-v1`;
- `intake-issue-12-v1`;
- `diagnostic-v1`;
- `curriculum-v2`;
- `publication-v1`;
- `assessment-topic-003-attempt-01`;
- `progress-after-topic-003`;
- `replan-goal-change-v1`;
- `migration-template-v4`.

Fill every required check for the selected profile with `passed`. Keep non-applicable reasoning in a short non-blocking note; do not remove required keys.

Set:

- `independent_pass: true`;
- `status: approved`;
- `blocking_findings: []`;

only after the separate review and corrections are complete.

## 6. Validate and merge boundary

Run:

- `python scripts/test_review_framework.py`;
- `python scripts/validate_review_framework.py`;
- every specialized validator required by the operation;
- the complete inherited workflow.

GitHub Actions calculates the generated diff from the pull request base. Missing review, partial coverage, stale hashes, unverified deletions, skipped checks or blocking findings prevent merge.

A successful phase response is allowed only after the approved review artifact, generated diff coverage, all required checks and safe merge are complete. Review details remain in GitHub unless they explain a blocker or the learner asks for them.
