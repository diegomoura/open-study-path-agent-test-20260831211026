# Publish tasks and selected integrations

Use the approved roadmap, topic contracts, ready lessons, integration plan and current state. Publication creates only the external organization that helps the learner act now. It must not regenerate pedagogical content.

Read `docs/learner-facing-language.md` before writing task descriptions or the completion response.

The natural command is:

`Organize minha trilha nas ferramentas que escolhemos.`

Continue accepting `Publique as tarefas da trilha nas integrações configuradas.` as an alias.

## Connection preflight

Run `instructions/42-integration-preflight.md` before external writes. Required providers must pass harmless verification. Optional providers are activated only when the learner supplied the information required to create a useful resource now.

Do not advertise, probe or summarize tools merely because they were mentioned in intake. Do not report an inventory of inactive integrations.

## Authority model

GitHub stores approved curriculum, lessons, assessments and verified progress. Exactly one task backend tracks operational execution. Reminders and calendars support routine only; they never establish learning completion.

## Standard assessment labels

Ensure labels exist:

- `assessment`;
- `assessment:submitted`;
- `assessment:graded`;
- `assessment:recovery-required`.

Do not create empty assessment issues during publication.

## Task backend

Create exactly one task for every approved roadmap topic in the single selected backend, including future topics whose detailed lesson is not materialized yet. The task is the learner's concise entry point into the path, lesson, practice and assessment. It is not an inventory of repository artifacts or integrations.

The published topic set must match the current approved roadmap. Before writing, calculate a stable roadmap fingerprint from the ordered topic IDs, visible lesson numbers, titles and direct prerequisite IDs. Persist that fingerprint with the board or project resource in `state/integrations.json`. A missing topic, extra topic, stale fingerprint or card from another curriculum blocks publication success.

### Human card titles and visible lesson numbering

Every learner-facing task title uses the roadmap lesson number and title:

`Aula 01 · <título da aula>`

Use at least two digits and expand naturally for paths with one hundred or more lessons. The visible lesson number is derived from the approved roadmap order and remains stable during synchronization. Keep `TOPIC-000` only in metadata, URLs and synchronization state; do not expose it in normal card titles.

Numbering is a navigation aid, not a prerequisite rule. Readiness, movement between lists and automatic materialization continue to use the dependency graph and each topic's direct prerequisite IDs. A numeração dos cartões ajuda a localizar a aula, mas nunca substitui os pré-requisitos diretos ou a posição do cartão no quadro.

### One primary resource per capability

For every ready topic, show these learner-facing capabilities in this order:

1. one **Aula** link to the complete module;
2. one **Prática** link only when a separate approved exercise or laboratory is useful;
3. one direct **Avaliação** link.

When practice is already contained in the lesson, do not create or link a duplicate deck. Never create flashcard Markdown, TSV exports or Quizlet sets. The **Aula** remains the practice destination in that case.

Do not show internal topic contracts, rubric YAML, state files or synchronization records.

### Primary next lesson and parallel availability

Resolve all topics whose direct prerequisites are currently satisfied. Among eligible topics, choose exactly one **primary next lesson**: the earliest unfinished eligible topic in approved roadmap order. Place only that card in **Próxima aula**.

Other unfinished eligible topics that already have complete reviewed learner resources belong in **Disponível em paralelo**. This makes independent roots visible without implying that a later-numbered lesson must be completed before an earlier dependency chain.

Eligible topics without complete reviewed learner resources remain in **Planejado** until automatic materialization finishes. Topics with unsatisfied direct prerequisites also remain in **Planejado**.

### Ready lesson card

Use a description equivalent to:

> **Você pode começar por aqui.**
>
> **O que você vai aprender:** <capacidade em linguagem clara>  
> **Tempo sugerido:** <estimativa>
>
> **Recursos**
>
> - **Aula:** <link direto para o módulo completo>
> - **Prática:** <somente quando houver um exercício separado útil>
> - **Avaliação:** <link direto para o formulário>
>
> **O que você vai produzir:** <entregável>  
> **Para concluir:** <critério de aplicação e pontuação em linguagem simples>
>
> Quando terminar, envie a avaliação e escreva:  
> **“Terminei <título da aula>. Avalie minhas respostas.”**

Create a checklist named **Sua sessão de estudo** using the three to seven granular actions from the module. The checklist intro may say:

> Siga estas etapas no seu ritmo. Os tempos são sugestões, não limites.

### Future lesson card

Build the copy from the topic contract's direct prerequisites, never from numeric adjacency.

The current visible label is **Pré-requisitos desta aula:**. Accept **Pré-requisitos desta etapa:** only as a migration alias from older task projections and normalize it when updating a card.

Use:

> **Pré-requisitos desta aula:** <títulos numerados dos pré-requisitos diretos em linguagem simples>.
>
> A numeração ajuda a localizar a aula. Para saber quando começar, siga os pré-requisitos acima e a posição do cartão no quadro.
>
> **O que você vai aprender:** <objetivo>  
> **Tempo sugerido:** <estimativa>  
> **O que você vai produzir:** <entregável>
>
> A aula completa será preparada automaticamente quando todos os pré-requisitos acima estiverem concluídos. Você não precisa pedir a geração manualmente.

The future card must stand on its own. Do not link nonexistent modules, PDFs, assessments or internal contracts.

### Trello structure

For a rich course, create or reuse one course board with lists equivalent to:

- Próxima aula;
- Disponível em paralelo;
- Planejado;
- Em estudo;
- Em avaliação;
- Revisão necessária;
- Concluído.

Only one unfinished card may be in **Próxima aula**. Preserve roadmap order inside **Disponível em paralelo** and **Planejado**. Use “Revisão necessária” in visible copy instead of “Recuperação” when the latter could sound punitive.

### Todoist or GitHub Issues

When another task backend is selected, preserve the same numbered title, primary-next indicator, parallel-ready distinction and projection rules. Todoist used as the primary task backend is distinct from Todoist used only for flexible reminders.

## Routine activation

Read `integration_preferences.routine` before creating reminders or calendar events.

### Fixed calendar blocks

Use Google Calendar or the approved calendar provider only when:

- `routine.mode` is `fixed_calendar`;
- days or dates, start time, duration and timezone can be resolved;
- the selected calendar is known;
- creating the event will not conflict with an explicit learner restriction.

Use the calendar event's own notification. Do not also create Todoist reminders for the same study block.

### Flexible reminders

Use Todoist reminders only when:

- `routine.mode` is `flexible_reminders`;
- recurrence or trigger and any requested reminder time can be resolved;
- the reminder points to the primary task or lesson.

Do not create Google Calendar events for the same routine.

### Missing routine details

When the learner chose a routine but required timing details are missing, ask one concise question before external writes. Do not mark the provider as configured, connected-and-ready or successfully published. A routine mode of `none` or `decide_later` activates neither calendar nor reminder provider.

## Email summaries

Email is an action available on explicit request, not a provider configured during publication. Do not create Gmail filters, drafts, schedules or automatic sends merely because Gmail is connected.

When the learner explicitly asks for an email summary, verify Gmail access at that moment, ask for any genuinely missing recipient or scope, and send or draft according to the request. Until then, keep `notifications.provider: chat` and `email_enabled: false`.

## Other integrations

Activate another optional tool only when it has immediate value in the ready content window and the learner must use it now. Research, artifact workspaces, external diagrams, habits and analytics remain absent unless a concrete current task requires them.

Never finish with a section equivalent to “O restante ficou assim”. Do not list inactive, deferred, reserved, fallback-only or merely connected providers. Mention a provider only when it gives the learner a destination now or when a real limitation changes the next action.

## Task projection review

Before publication success, read the board or project and every created or updated task back when supported and verify:

- the external task count equals the approved roadmap topic count;
- every approved topic ID appears exactly once in synchronization metadata;
- visible titles follow `Aula NN · <título>` and match roadmap order;
- exactly one unfinished eligible card is in **Próxima aula**;
- other materialized eligible cards are in **Disponível em paralelo**;
- blocked or not-yet-materialized cards are in **Planejado**;
- objective, effort and deliverable match;
- prerequisite copy contains exactly the direct prerequisite titles;
- resource order is Aula, optional Prática, Avaliação;
- links point to current reviewed content and future cards contain no broken resource links;
- no internal artifact or inactive provider is exposed;
- the persisted roadmap fingerprint matches the current approved roadmap.

Correct mismatches before continuing. Persist direct prerequisite IDs, visible lesson number and current content version with each task resource so later synchronization can detect drift.

## Idempotency and state

Inspect `state/integrations.json` and matching provider resources before writing. Reuse or update exact resources when supported. Store capability, provider, safe ID, URL, topic, visible lesson number, content version, direct prerequisite IDs, roadmap fingerprint, authority, sync status and timestamp. Never persist credentials, tokens, OAuth details, raw submissions or unnecessary identity data.

Task synchronization is idempotent. An interrupted publication must report and reuse what was actually created. A board whose persisted roadmap fingerprint differs from the approved roadmap is stale: do not silently treat its cards as the current course. Update it only when the learner asked to synchronize that board; otherwise create the newly requested canonical board and record its identity.

## Persist publication completion

The lifecycle may advance to evaluation only after the required task projection is durably recorded and its review has no blocking mismatch.

After the complete required publication set succeeds:

- set `sync.status` to `success`;
- set `sync.last_success_at` to the current ISO 8601 timestamp;
- clear resolved entries from `sync.errors`;
- retain safe resource IDs and URLs needed for idempotent updates.

Do not make inactive reminders, calendars, email or other optional providers part of publication success.

When required publication is blocked, failed, partial or still in progress:

- do not set success or `sync.last_success_at`;
- persist the accurate status and a short non-sensitive reason;
- do not present an evaluation command;
- return the provider-specific connection or retry command.

Run `scripts/lifecycle_next_action.py` against the final persisted state before composing the completion response.

## Completion

After publication, answer in this order:

1. what is ready;
2. the primary task destination;
3. the first concrete action;
4. the natural evaluation command;
5. one attention item only when it changes that action.

A good response is equivalent to:

> Sua trilha está organizada no <ferramenta principal>.
>
> <link do quadro ou tarefa>
>
> Comece por **Aula 01 · <título da primeira aula>** e mova a tarefa para **Em estudo** quando iniciar.
>
> Quando terminar a aula e enviar a avaliação, escreva:
>
> `Terminei <título da aula>. Avalie minhas respostas.`

Do not lead with a publication report, provider inventory, PR status or CI result.
