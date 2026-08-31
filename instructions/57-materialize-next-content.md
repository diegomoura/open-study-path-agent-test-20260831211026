# Materialize the next content window

Run this instruction automatically inside a successful topic-evaluation operation. It is not a separate user-facing phase and must not require another command.

## Purpose

Keep the approved roadmap complete while generating detailed teaching content only slightly ahead of the learner. This preserves coherence, reduces oversized pull requests and lets future lessons incorporate verified assessment evidence and integration fallbacks.

Every newly materialized lesson must pass `instructions/36-review-course-content.md` before merge. Materialization and course-content review are distinct responsibilities inside the same operation.

## Configuration

Read `content_generation` and `content_review` from `.open-study-path/instance.yml`, plus `study.config.yml`, `study/integrations.md` and `state/integrations.json`.

Defaults when missing:

- `strategy: adaptive_rolling_window`;
- `lookahead_topics: 2`;
- `full_upfront_max_topics: 4`;
- `full_upfront_max_hours: 4`;
- `adapt_future_modules_from_assessments: true`;
- `visual_learning.mermaid_enabled: true`;
- `visual_learning.minimum_diagrams_per_materialized_module: 1`;
- `visual_learning.diagrams_must_be_explained: true`.

For `adaptive_rolling_window`, a curriculum at or below both full-upfront thresholds may materialize every topic during initial generation. Larger curricula must maintain a rolling window.

## Rolling-window calculation

After a topic is mastered:

1. read `study/roadmap.md`, every topic contract and `state/progress.json`;
2. identify topics whose `content_status` is `materialized` but which are not yet mastered;
3. identify planned topics in deterministic topological order;
4. select the next planned topic only when every prerequisite is already mastered or is itself materialized inside the lookahead chain;
5. materialize enough selected topics to restore `lookahead_topics`, unless no eligible planned topic remains.

Do not count recovery material as a normal lookahead topic. Do not materialize blocked branches merely to fill the number.

A topic number does not make the numerically previous topic a prerequisite. Use the direct prerequisite list in each topic contract. In a branched graph, more than one topic may become eligible after the same prerequisite.

## Inputs for a new module

Use all of these sources:

- the approved roadmap and topic contract;
- the topic's stable learning outcome IDs and required concepts;
- intake and diagnostic evidence;
- verified assessment results and recovery history;
- `templates/module.md`, `templates/assessment-rubric.yml`, `templates/topic-assessment-issue-form.yml` and `templates/content-review.yml`;
- `templates/integrations-plan.md` and `docs/integration-capabilities.md`;
- `docs/mermaid-visual-learning.md`;
- previously approved modules as consistency references.

A previous module is not the sole template. Do not copy its structure mechanically when the next capability requires a different teaching or visual approach.

Assessment evidence may adapt examples, emphasis, prerequisite retrieval, practice difficulty, visual representations and formative-practice emphasis. It must not silently rewrite the approved objective, prerequisites, learning outcomes, required concepts, deliverable, effort or mastery criteria. A structural pedagogical change belongs to replan.

## Optional research during materialization

When the next topic contains empirical or scientific claims and Consensus is selected, perform a harmless optional availability probe. Use it to discover supporting research only when available. If unavailable, continue with primary sources, official documentation and web research.

Every selected reference must be persisted with a precise locator in the module. An external research response is not itself a durable citation and cannot change the approved topic contract.

## Required repository changes

For every selected topic:

1. create the complete module;
2. include at least the configured minimum number of useful Mermaid diagrams and explanatory prose;
3. preserve every approved learning outcome and place exactly one hidden `open-study-path:outcome` marker beside content that genuinely teaches it;
4. create a durable TSV flashcard file when the topic contains meaningful atomic recall material and formative practice is selected or recommended;
5. create the 100-point rubric and map every question with valid `outcome_ids`;
6. create the discoverable assessment Issue Form with the topic marker and standard assessment labels;
7. set the topic's `content_status` to `materialized`;
8. increment `content_version` and set `materialized_at`;
9. create or refresh `state/content-reviews/TOPIC-000.yml` only after the independent course-content review passes for the current content version;
10. update the roadmap's materialization status without changing the approved graph;
11. update `study/integrations.md` only when verified evidence changes a recommendation, fallback or topic-specific integration use.

The module must contain three to seven focused execution actions, normally 10–25 minutes each. The topic should normally represent 45–90 minutes of coherent learning. Split a topic before approval when it exceeds 120 minutes and can be separated into independently assessable capabilities.

For nontechnical subjects, use Mermaid for decision paths, causal relationships, conceptual maps, timelines or state changes. For programming, AWS and other technical subjects, choose architecture, dependency, sequence, state, class or data-flow views. Complex topics should use multiple focused diagrams rather than one crowded diagram.

Every lesson diagram must render in GitHub, be introduced in context and be followed by an explanation of what the learner should notice. Do not create decorative or purely illustrative diagrams.

## Independent course-content review

After lesson, practice and assessment authoring:

1. switch to `instructions/36-review-course-content.md`;
2. compare the topic contract, module, rubric, Issue Form, flashcards and proposed task projection;
3. verify that prerequisite retrieval uses only direct prerequisites and that navigation does not assume linear numbering;
4. verify each outcome marker is beside substantial teaching content;
5. verify every rubric mapping genuinely measures the declared outcome;
6. correct blocking findings and rerun the review;
7. write the approved evidence to `state/content-reviews/` for the exact current content version.

A stale review, missing outcome, mismatched prerequisite list or unresolved blocking finding prevents merge.

## Pull request and validation

Create a small draft pull request limited to:

- the selected topic contracts;
- their new modules, optional flashcard files, rubrics and assessment Issue Forms;
- their current course-content review artifacts;
- the roadmap materialization status;
- integration-plan changes justified by the new topic or verified evidence;
- the shared assessment-operation review artifact.

Run the curriculum validator, course-content review validator and all required checks. Review Mermaid syntax, source precision, flashcard quality, outcome traceability and integration authority alongside the rest of the content. Correct the branch. Under `workflow.curriculum_merge_policy: agent_review_then_merge`, mark ready and merge when CI passes and no new pedagogical or integration-policy decision is required.

Do not ask the owner for a separate generation, review or merge command.

## Capability synchronization

After repository materialization succeeds, synchronize selected providers from the approved plan. Run harmless probes first. Repository materialization is already successful and must never be undone by an optional provider failure.

### Authoritative task backend

- update the existing topic task with the module first, then one primary practice resource and assessment form;
- replace the planning checklist with the granular execution plan;
- move only newly dependency-ready topics to the provider's ready state;
- preserve the direct prerequisite list in task state and learner copy;
- never create a second authoritative task in another provider.

### Auxiliary Todoist reminders

Create or update only recurring review or study reminders when selected. Link to the authoritative task or module and persist `authority: reminder_only`.

### Scheduling

Update existing Reclaim, Google Calendar or Outlook Calendar resources instead of creating duplicates. Respect free-tier policy. When Reclaim is unavailable, use the approved calendar fallback or omit external scheduling.

### Formative practice

Create or update Quizlet sets from the current TSV content version when connected. If unavailable, keep the local flashcard link. Ace Quiz Maker remains optional and does not need durable synchronization.

### Habits

Create or reuse at most the configured number of Habitify habits. Persist `authority: consistency_only`. Do not create one habit per topic.

### External visuals and artifacts

Update Whimsical or another external visual only when the plan identifies a concrete use; Mermaid remains canonical. Create or update Drive/Notion/SharePoint/Dropbox deliverable artifacts only when the topic requires them.

### Airtable projection

Project new topics, attempts, sessions or resource metadata only after GitHub state is committed. Use `github_to_airtable`; include source and content version. Airtable cannot change mastery, score or curriculum.

### Course resources and notifications

Keep precise course-discovery links from the approved module. Update email summaries only when selected and connected; chat is the fallback.

## Idempotency and failure handling

Before every write, inspect `state/integrations.json` and exact matching provider resources. Reuse or update resources and record capability, provider, type, external ID, URL, topic, content version, authority, sync status and timestamp.

A missing optional connector records a deferred or fallback sync and does not block the next topic. A missing required authoritative task provider may pause only that external synchronization; it must not hide or invalidate the ready module and GitHub assessment.

## Completion

Return the topic-evaluation result together with the next available module, authoritative task and assessment form. Mention the internal materialization PR only as an artifact. Briefly name any optional fallbacks used, but do not ask for another command before the learner starts the next topic.
