# Topic-first planning and safe external publication

Use this contract during curriculum generation, integration preflight, task publication and partial-publication recovery.

## Topics are the course structure

`planning.unit: topic` is authoritative. Organize the learning path as areas, dependency-aware topics, lessons, activities, evidence and assessments.

The intake may contain a routine preference under `integration_preferences.routine` and an optional free-text `path.time_constraints` value such as a relevant date or approximate weekly availability. Neither value authorizes inventing:

- a fixed course duration in weeks;
- week-numbered structural groups;
- a weekly roadmap table;
- deadlines, due dates or an implied late state;
- Trello lists, labels or cards organized by week.

A time constraint does not authorize silently removing mastery-required topics, reducing evidence requirements or claiming that an unrealistic scope fits. Generate the complete dependency-aware course. When the constraint is useful, identify a priority order and explain feasibility honestly.

Without an explicit learner request for a dated projection, show total estimated effort and effort per topic. Say that the pace is flexible and follows prerequisites and verified progress.

## Stable visible lesson order

Assign every approved roadmap topic a stable learner-facing lesson number based on its position in the approved roadmap. Task tools and course navigation use `Aula 01 · <título>`. Internal files, links and state continue using the stable topic ID.

The lesson number helps the learner locate content. It does not create a prerequisite edge and does not mean every lower number must be completed first.

At each publication or progress update:

1. calculate every unfinished topic whose direct prerequisites are satisfied;
2. choose the earliest eligible topic in roadmap order as the single primary next lesson;
3. classify other eligible materialized topics as available in parallel;
4. keep topics with unmet prerequisites or incomplete reviewed learner resources as planned.

A course may materialize more than one independent root in the initial window. That is valid, but the task interface must show one **Próxima aula** and separate the other roots under **Disponível em paralelo**.

## Routine preference is not a complete schedule

The routine mode determines one support path:

- `fixed_calendar` → one calendar provider;
- `flexible_reminders` → Todoist reminders;
- `none` or `decide_later` → neither;
- `custom` → interpret the learner's description before choosing.

Do not activate both calendar blocks and Todoist reminders for the same routine. When required values are absent, collect the minimum missing scheduling details at activation.

For a fixed calendar block, resolve days or dates, start time, duration, timezone and selected calendar. For a flexible reminder, resolve recurrence or trigger and any requested reminder time. Never create empty placeholder events or tasks.

When the learner explicitly requests a dated or weekly projection, keep topics as the canonical structure and add this hidden marker to the optional projection:

`<!-- open-study-path:calendar-projection explicitly_requested=true -->`

A date or availability statement is a constraint to discuss, not permission to silently invent a week-by-week plan.

## Required-operation preflight

Before the first external write, inspect the connector operations actually available for the complete required publication set.

For a Trello task backend, confirm that the connector exposes operations needed to:

1. read or find the canonical board;
2. create and read lists;
3. create and read cards;
4. create checklists when the approved card contract requires them.

A successful board-list read proves connection only. It does not prove that list, card or checklist publication can finish. If any required operation is unavailable or its required identifiers cannot be obtained, stop before creating the board.

The complete required publication set contains exactly one task for every approved roadmap topic, not only materialized topics. Before writing, calculate an ordered roadmap fingerprint from lesson number, topic ID, title and direct prerequisite IDs. Persist it with the board or project resource and verify it after publication.

## No disposable production probes

Never create `tmp`, `test`, `probe`, numbered variants or any other disposable board, list, card, event or workspace to discover a connector schema or test access.

Use harmless reads and the exposed tool schema. When no harmless operation exists, the first write must be an intended canonical resource that can be adopted immediately and recorded durably.

## Journal every successful write

After each successful external creation or update, persist its safe identifier, URL, capability, provider, type and status in `state/integrations.json` before the next external write.

For a newly created task board, also set `integrations.task_manager.board_or_project` in `study.config.yml` immediately. Store the ordered roadmap fingerprint, visible lesson numbers and topic associations with the board. This journal is required even when the broader publication later becomes partial or blocked.

An interrupted run must be resumable from recorded state and must reuse the exact board, lists, cards, reminders or events already created. Never wait until final success to record resources.

## Unexpected side effects and cleanup

After an unexpected external creation:

1. stop further exploratory writes;
2. record the exact resource identifier and URL;
3. attempt safe cleanup in the same operation only when the connector exposes a supported archive or delete action and the resource is unambiguously agent-created;
4. otherwise mark the resource as orphaned and keep cleanup as an explicit technical pending action;
5. never make the learner reconstruct what was created from names alone.

The agent owns cleanup of its own probes whenever the connected capability permits it. Do not present manual deletion as a normal learner responsibility.

## Partial publication response

Do not speculate about quotas, workspace limits, permissions or provider defects without verified evidence.

When the canonical resource exists but publication is incomplete:

- state what is usable now;
- state what remains unpublished only when it changes the next action;
- confirm internally that the existing resource was recorded and will be reused;
- mention cleanup only when it changes the learner's next action;
- return the state-derived command from `scripts/lifecycle_next_action.py`.

The natural continuation for a recorded partial publication is:

`Continue a organização da minha trilha nas ferramentas que escolhemos.`

Do not require the learner to repeat a board URL or technical identifier.
