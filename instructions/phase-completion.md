# Guided phase completion

Use this contract at the end of every lifecycle phase. Read `docs/learner-facing-language.md` before composing the response.

## Internal completion

Finish validation, review, correction, safe merge and configured rolling-window materialization before responding. Pull requests, checks and repository state remain the technical audit trail.

Read `instructions/04-review-generated-artifacts.md` and run the phase profile declared in `instructions/manifest.yml`. A successful operation requires an approved review artifact and generated diff coverage for every generated instance artifact changed by the operation. Missing review, partial coverage, stale artifact fingerprints, a skipped required check or any blocking finding blocks merge and blocks a successful response.

Verify every required check for the current unchanged pull-request head. If any required check is failing, pending, cancelled, missing or cannot be verified, the phase is blocked. Do not merge and do not send a successful phase response. Never treat a correct-looking diff, an earlier green commit or a future default-branch run as validation of the current head.

Do not send a transition message immediately before repository work. Complete the operation and send one final response.

## Automatic completion for every phase

Resolve the current phase, suboperation and merge policy from `instructions/manifest.yml` and `.open-study-path/instance.yml`.

When the resolved policy is listed under `automatic_completion.automatic_merge_policies`, run `instructions/03-await-ci-and-merge.md` and `scripts/ci_completion_state.py`. This requirement applies to every lifecycle phase and suboperation.

The automatic completion sequence must:

1. capture the final reviewed head as `expected_head_sha`;
2. mark the pull request ready before attempting auto-merge;
3. observe only required checks attached to that exact head;
4. merge with `expected_head_sha` as an atomic precondition;
5. verify persisted lifecycle state on the default branch.

A changed head invalidates every earlier observation. A closed pull request alone does not prove phase completion. Do not release the next lifecycle command until the state machine returns `complete`.

## Learner-facing response

A successful response should answer, in this order:

1. **What is ready** — one short sentence focused on the learner's outcome.
2. **Where to go** — the one or two links needed now.
3. **What to do next** — a concrete next action.
4. **Continue naturally** — one short, single copyable continuation.
5. **Attention** — only when a real decision, missing connection or limitation changes the next action.

Do not foreground PR numbers, CI, commit hashes, branches, changed files, validator names, internal states or synchronization metadata after success. Provide technical details only when requested or when they explain a blocker that requires action.

Do not append a provider inventory. Inactive, deferred, fallback-only, reserved or merely connected tools stay in repository state. Mention a tool only when it gives the learner a destination now or changes the next action.

## Resolve the next action from persisted state

Persisted lifecycle state, not a previous conversational suggestion, determines the next operation. Before composing the final response, read `.open-study-path/instance.yml` and `state/integrations.json` and apply `scripts/lifecycle_next_action.py`.

An agent-authored phrase such as `sem publicar tarefas ainda` deliberately defers publication for one operation; it is not a learner decision to skip publication permanently. The agent owns that deferral and must surface the deferred publication as the next action after detailed curriculum generation.

The normal routing invariant is:

- diagnostic complete and curriculum proposal not approved → proposal suboperation inside `generate`;
- curriculum proposal approved but detailed curriculum not generated → detailed generation inside `generate`;
- curriculum generated and publication not completed → `publish`;
- publication completed successfully → `evaluate`.

The proposal and detailed generation share the lifecycle phase `generate`, but they have different persisted states and different commands. Never repeat the proposal command after `curriculum_proposed` and `curriculum_approved` are true. Never skip directly from an approved proposal to publication while `curriculum_generated` is false.

Publication is complete only when `state/integrations.json.sync.status` is `success`, `succeeded` or `completed` and `last_success_at` is present. Missing, `not_started`, pending, partial, blocked or failed publication state cannot enable evaluation.

When publication is pending, do not present an assessment submission or evaluation command as the next action. Do not include `Terminei <título da aula>. Avalie minhas respostas.` while publication is pending. The single copyable continuation remains the publication command.

## Technical review state

Operational review occurs internally. Record review and merge status in GitHub and do not require a fixed PR-status sentence in the learner-facing response.

When a genuine unresolved decision exists, link the exact PR or comment and say plainly what decision is needed. Never ask the owner to review an entire PR merely because one exists.

A command containing `Abra um pull request` identifies the audit mechanism, not a request to leave the pull request open. Under `agent_review_then_merge`, review, correct, validate, mark ready and merge automatically unless the learner explicitly asks to keep it open or a concrete material decision remains unresolved.

## Natural commands

Present natural commands by default and accept older technical commands as aliases.

### After intake setup

Return the direct intake link and use:

`Preenchi o formulário. Pode continuar.`

Do not ask for an issue or submission number unless deterministic lookup finds more than one valid candidate.

### After intake import

When diagnostic chaining was authorized, start the bounded diagnostic and ask the first short question. Otherwise use:

`Vamos fazer meu diagnóstico.`

### After diagnostic

Use:

`Gere uma proposta de trilha com base no intake e no diagnóstico. Abra um pull request e não publique tarefas ainda.`

This command creates, independently reviews, validates and merges the roadmap proposal. `Não publique tarefas ainda` restricts only the later publication operation.

### After approved curriculum proposal

State that the roadmap architecture is approved and that detailed lessons and external tasks have not been created yet.

Use:

`Crie minha trilha de estudos.`

This state means curriculum proposal approved but detailed curriculum not generated.

### After curriculum generation

State whether all lessons or only the first lessons are ready. Link the roadmap and first ready lesson when useful. Summarize only tools that help now.

If publication was previously deferred, say plainly that organization in the selected task tool remains pending. Use this as the only normal copyable continuation:

`Organize minha trilha nas ferramentas que escolhemos.`

Do not include `Terminei <título da aula>. Avalie minhas respostas.` in this response.

### When required publication is blocked

Name only the service that needs attention and explain its practical effect. Use a natural return command such as:

`Conectei o Trello. Pode continuar.`

Re-run access verification; a learner statement alone does not prove connection.

### After task publication

Link the primary task destination and direct the learner to the first ready lesson. Do not lead with a publication report or a list of providers.

Use:

`Terminei <título da aula>. Avalie minhas respostas.`

Continue accepting:

- `Finalizei o TOPIC-000. Avalie minhas respostas.`

A good response is equivalent to:

> Sua trilha está organizada no <ferramenta principal>.
>
> <link do quadro ou tarefa>
>
> Comece por **<título da primeira aula>** e mova a tarefa para **Em andamento** quando iniciar.
>
> Quando terminar a aula e enviar a avaliação, escreva:
>
> `Terminei <título da aula>. Avalie minhas respostas.`

### After topic evaluation

Report the score, strongest evidence, most important improvement and next ready lesson or focused review. When mastered, restore the configured lookahead automatically.

Natural commands:

- `Terminei <título da aula>. Avalie minhas respostas.`
- `Terminei a revisão de <título da aula>.`

Only request an explicit issue number when multiple valid candidates remain.

## Routine and email attention

When the learner selected a fixed calendar or flexible reminder routine but required timing details are missing, the attention item must be one concise question that collects them. Do not claim the provider is configured.

Gmail is not configured during normal publication. It is an available action only after an explicit request to send or draft a summary. Do not mention Gmail in a successful publication response unless the learner asked for an email action.

## Optional connection suggestions

Use Plugin Management only for selected optional providers with immediate value in the ready content window. Do not suggest inactive, declined, forbidden, irrelevant or already connected providers. Show at most one suggestion per provider and at most three in one response.

## Concision and visibility

Detailed provider explanations, source mappings, scores, diffs, PR state and synchronization metadata belong in repository artifacts. Surface them only when they change what the learner should do now.

Internal logs and diagnostic ZIP files are debugging aids. Do not attach or foreground them after success.

<!-- Compatibility markers: Next step; Continue command; Concision rule; auto_when_unambiguous; Do not send a separate transition message. -->
