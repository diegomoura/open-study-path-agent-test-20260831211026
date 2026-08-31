# Agent Operating Contract

Read this file before changing this repository or an instance derived from it.

## Repository mode

The canonical repository is template mode when `.open-study-path/template.yml` exists and `.open-study-path/instance.yml` does not. It may improve reusable contracts, but must not contain learner-specific state or curriculum.

An instance is valid only when `.open-study-path/instance.yml` exists. Its `repository` field is the persistent identity. Stop writes when it conflicts with the explicit Project repository.

Repository metadata such as reported size, code-search status, search results or an incomplete local checkout is not authoritative evidence that a repository is empty. Before setup writes, read `.open-study-path/template.yml`, `.open-study-path/instance.yml`, `AGENTS.md`, `instructions/manifest.yml` and `.github/ISSUE_TEMPLATE/create-study-path.yml`.

A derived instance retains `.open-study-path/template.yml`; the instance marker takes precedence. Never delete reusable workflows, validators, schemas, templates, instructions or documentation during normal setup. Apply `instructions/02-setup-execution.md` during the first chat.

A GitHub intake is ready only when the checked-in form contains the current repository form contract marker, explains that the course name comes from the issue title and repository labels `study-request` and `intake:imported` exist. Provision missing labels before reporting setup success. The marker identifies the form file and is not emitted into a submitted issue body. During import, require the automatic label, complete expected rendered structure, non-empty required responses, checked consent, a valid title and unimported state. Preserve the issue title as `path.name`, preserve the complete main answer as `path.learning_request` and derive only a concise `path.subject`. Matching headings alone never prove intake identity. Never ask the learner to edit an issue to add a technical marker.

## Guided lifecycle

Read `instructions/manifest.yml`, `instructions/phase-completion.md`, `instructions/31-topic-first-safe-publication.md` and `docs/learner-facing-language.md` before lifecycle work.

Internal validation, review, correction, safe merge and rolling materialization belong to the active operation. Complete them before responding.

The learner-facing response describes what is ready, where to go and what to do next. Do not lead with PR, CI, hashes, branches, changed files or internal classifications after success. Technical details remain in GitHub and are surfaced only when requested or required to resolve a blocker.

Resolve the next learner command from persisted state with `scripts/lifecycle_next_action.py`. Curriculum generation does not authorize evaluation while publication remains incomplete. A recorded partial publication must return the resume command and reuse every recorded external resource.

When the agent itself suggested `sem publicar tarefas ainda`, that phrase is a one-operation safety deferral. The agent must restore publication as the next visible action after generation; never treat its own suggestion as a learner decision to skip integrations.

## Independent review framework

Read `docs/review-framework.md` and `instructions/04-review-generated-artifacts.md` for every artifact-producing lifecycle, migration or synchronization operation.

Every generated artifact changed by an instance operation must be covered by an approved review artifact changed in the same pull request. Store durable review evidence under `state/reviews/` using the phase profile declared in `instructions/manifest.yml`.

Authoring and review are separate passes even when the same runtime performs both. The reviewer reconstructs evidence from approved inputs, repository outputs and harmless external read-backs; it does not trust the authoring pass's success claim.

Specialized review remains additive: materialized teaching content requires `instructions/36-review-course-content.md`, and selected integrations require resolution and projection checks.

Missing review, partial coverage, stale fingerprints or skipped checks block CI, merge and a success response.

## Setup, intake and diagnostic

- Never convert the canonical template into an instance.
- Never request API keys, tokens or passwords.
- Import only an approved intake source.
- Preserve the complete learning request separately from its concise subject label.
- Persist structured summaries, not raw submissions or diagnostic transcripts.
- Treat diagnostic as bounded placement, not teaching.
- Ask one short question at a time.
- For beginner or no prior knowledge, target 3–5 and hard-limit 7 unless comprehensive assessment is explicitly requested.
- Do not recommend or probe providers before diagnostic and curriculum context exist.

## Roadmap and adaptive content

Initial generation creates the complete roadmap, every topic overview and an integration plan. Detailed lessons follow the configured content-generation strategy.

Keep internal `planned` and `materialized` values in metadata. In visible copy use “aula futura” and “aula pronta”.

Read `instructions/31-topic-first-safe-publication.md` before generating or revising a roadmap. `planning.unit: topic` is authoritative. Do not create fixed durations in weeks, week-numbered groups or weekly roadmap tables unless the learner explicitly requests a calendar projection. An optional time constraint may guide priority and feasibility language, but it must not silently remove mastery-required content or redefine partial coverage as completion.

Every approved roadmap topic receives a stable learner-facing lesson number derived from roadmap order. Use `Aula 01 · <título>` in task tools and other navigation surfaces. Keep `TOPIC-001` as the stable internal identifier in files, metadata and links. The visible number helps navigation; it never replaces the dependency graph or direct prerequisite list.

A topic number is not a prerequisite rule. The dependency graph and each topic's direct prerequisite list are authoritative. A later-numbered independent root may be available in parallel while the primary sequence continues through an earlier-numbered dependency chain.

## Granularity and teaching quality

A topic is one coherent independently assessable capability. Use three to seven focused actions, normally 10–25 minutes each, and prefer 45–90 minutes per topic.

Read `docs/beginner-first-pedagogy.md`. A topic overview is not a lesson. Every ready module must teach with:

- personal orientation and clear outcome;
- first-principles onboarding when required;
- progressive vocabulary and acronym expansion;
- prerequisite retrieval;
- explanatory content and nuance;
- a bounded analogy or labeled concrete example;
- at least two worked examples;
- useful Mermaid visual models;
- misconceptions and corrections;
- guided and independent practice;
- active recall inside the lesson;
- deliverable and assessment instructions;
- provenance, inspected sources and useful alternative formats.

Do not generate flashcards, Markdown decks, TSV exports or Quizlet sets. Recovery practice stays inside the lesson and assessment unless a genuinely different exercise or laboratory adds value.

Read `docs/content-quality-and-sources.md`. Every ready lesson normally uses three to seven curated sources, including a primary or official source when available and a reliable explanatory source. Do not cite plugin responses instead of original sources, add uninspected links or invent citations.

## Independent course-content review

Read `instructions/35-review-curriculum.md` and `instructions/36-review-course-content.md` as different roles.

The curriculum reviewer verifies scope, graph, topic contracts and architecture. The course-content reviewer verifies that every materialized lesson, practice and assessment delivers what the contract promised.

Every topic defines stable learning outcomes and required concepts. Every materialized lesson contains one hidden outcome marker per approved outcome, every rubric question maps to outcomes and every materialized topic has a current content review under `state/content-reviews/`. A stale review, missing outcome, false prerequisite, navigation mismatch or blocking finding prevents merge.

## Mermaid visual learning

Every roadmap contains the actual topic dependency graph. Every ready module contains the configured minimum number of explained Mermaid diagrams. A diagram supplements prose and practice; it does not replace them.

## Capability-based integrations

Read `docs/integration-capabilities.md`, `study.config.yml`, `study/integrations.md` and `state/integrations.json`.

GitHub stores curriculum, lessons, assessments and verified progress. Exactly one task backend tracks execution.

- The default backend is GitHub Issues, proposed to nobody proactively; Trello and Todoist are optional upgrades activated only on explicit request or connection, with repository Markdown as the final internal fallback.
- The task backend projects every approved roadmap topic exactly once, including future lessons without learner-resource links.
- Persist the current ordered roadmap fingerprint with the board or project and reject a stale or different curriculum as the current projection.
- `integration_preferences.routine.mode: fixed_calendar` uses one calendar provider and its event notification.
- `integration_preferences.routine.mode: flexible_reminders` uses Todoist and creates no duplicate calendar event.
- `none` and `decide_later` activate neither routine provider.
- Missing day, time, duration, recurrence or timezone is collected with one concise question before creation.
- Gmail is available only on explicit request to send or draft a summary; connector availability is not a configured email policy.
- Mermaid remains canonical.
- Airtable remains a one-way `github_to_airtable` projection.

When `integration_preferences.account_connections` is `no_external_accounts`, do not suggest, probe or write to apps requiring another account. Use GitHub Issues or repository Markdown, Mermaid, repository artifacts, primary sources, web research and chat.

Optional providers never block the GitHub or Markdown path. Before external writes, run `instructions/42-integration-preflight.md` and `instructions/31-topic-first-safe-publication.md`. Store only safe external identifiers and synchronization metadata.

Never create disposable external probe resources. Persist every successful external write before starting the next one.

## Repository execution and review

Read `instructions/32-generation-execution.md` for generation and materialization. Keep every commit within phase scope. Do not modify reusable workflows, validators, instructions, templates or schemas from an instance curriculum operation.

For every operation PR, correct resolvable issues, run specialized review, run the shared phase review, validate generated diff coverage and merge under the configured policy when no genuine decision remains.

For every repository phase, inspect required checks for the current unchanged PR head. A failing, pending, cancelled, missing or unreadable required check blocks merge and blocks a success response. Never merge because the diff looks correct while CI is red or unknown.

## Publication and task language

Read `instructions/40-publish-tasks.md`, `instructions/42-integration-preflight.md` and `instructions/31-topic-first-safe-publication.md`.

Create exactly one task per approved roadmap topic. Every visible task title uses `Aula NN · <título>` with the stable roadmap lesson number. Keep topic IDs internal. Numbering is mandatory in task backends even for branched courses, but readiness always follows direct prerequisites.

For Trello, use lists equivalent to:

- Próxima aula;
- Disponível em paralelo;
- Planejado;
- Em estudo;
- Em avaliação;
- Revisão necessária;
- Concluído.

Exactly one unfinished eligible topic occupies **Próxima aula**: the earliest eligible topic in roadmap order. Other eligible materialized roots or branches occupy **Disponível em paralelo**. Topics with unmet prerequisites or without complete reviewed learner resources remain in **Planejado**.

### Human task titles

A ready card says what the learner will do, how long it may take, where the complete lesson, optional separate practice and assessment are, what to produce and how to finish.

Show resources in this order: **Aula**, optional **Prática**, **Avaliação**. Do not create a duplicate practice resource when the exercises already live in the lesson.

A future card begins with **Pré-requisitos desta aula**, lists exactly the direct prerequisite titles and explains that numbering helps navigation while the list position and prerequisites determine readiness. Do not attach nonexistent lesson, practice or assessment links.

A task backend is not a repository inventory. Do not link topic contracts, rubric YAML, state files or synchronization records.

After successful publication, do not add “O restante ficou assim” or list inactive, deferred, reserved, fallback-only or merely connected providers. Show the primary destination, first action and evaluation command.

Natural commands presented to the learner, in lifecycle order:

- `Preenchi o formulário. Pode continuar.`
- `Vamos fazer meu diagnóstico.`
- `Crie minha trilha de estudos.`
- `Organize minha trilha nas ferramentas que escolhemos.`
- `Continue a organização da minha trilha nas ferramentas que escolhemos.`
- `Terminei <título da aula>. Avalie minhas respostas.`
- `Terminei a revisão de <título da aula>.`

Do not present a later command while an earlier required phase remains incomplete.

## Assessment resolution

Read `instructions/55-evaluate-topic.md`. Resolve submissions using labels, hidden marker, history and title as a consistency signal. Never choose an arbitrary newest issue. Ask for an issue number only when multiple valid candidates remain.

Grade every response independently, calculate 0–100, comment on the issue, persist a versioned attempt and update progress. No external provider sets completion.

When mastered, run `instructions/57-materialize-next-content.md` automatically and return the next ready lesson. When more work is needed, create focused review and targeted reassessment using supportive language such as “Revisão necessária”.

## Agent model configuration

Read `docs/agent-model-configuration.md` when a repository operation is executed by a
real agent call instead of a manual conversation. `.open-study-path/models.yml` (optional;
falls back to the recommended tier from `templates/agent-models.yml` when absent) selects
which Claude model tier each agent role uses. `scripts/agent_model_resolution.py` is the
single source of truth for the recommended tier per agent and never performs I/O or calls
an API itself. `scripts/validate_model_config.py` validates the schema and surfaces a
non-blocking warning whenever a structural agent (`curriculum_architect`,
`curriculum_reviewer`, `content_author`, `content_reviewer`, `evaluate`) is configured
below its recommended tier. The warning documents a deliberate cost/quality choice; it
never blocks CI.

`track` (`instructions/50-track-progress.md`) is Haiku and not structural: it
synchronizes state against well-defined transition rules (mastery only from a verified
evaluation; external activity such as a checked task, reminder or habit streak is never
sufficient alone), the same class as `publish`/`integration_preflight` rather than
`curriculum_architect`/`evaluate`.

## Agent-pilot dispatch

Every phase above runs as an isolated Claude API call through the GitHub Actions
workflows described in `docs/claude-agent-pilot.md`. This is the only operating mode:
the earlier manual chat flow was removed entirely (Etapa 8). Human onboarding is
`docs/claude-agent-setup.md` (`ANTHROPIC_API_KEY` repository Secret).

## Safety

Never commit credentials, secrets, raw submissions, original uploaded files, diagnostic transcripts or unnecessary personal data. Prefer pull requests for structural and material changes. Ask before destructive operations.
