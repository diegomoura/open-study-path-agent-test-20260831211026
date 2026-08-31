# Generate and approve learning path

Generate a complete dependency-aware roadmap and concise contract for every topic. Materialize detailed teaching content according to the configured strategy. Generate a contextual integration plan, but do not publish external resources during this phase.

Read before generating:

- `docs/learner-facing-language.md`;
- `docs/beginner-first-pedagogy.md`;
- `docs/content-quality-and-sources.md`;
- `docs/mermaid-visual-learning.md`;
- `docs/integration-capabilities.md`;
- `instructions/35-review-curriculum.md`;
- `instructions/36-review-course-content.md`.

## Planning contract

Always create upfront:

- `study/roadmap.md` with the complete topic graph and estimated effort;
- one concise contract per topic under `study/topics/` using `templates/topic.md`;
- observable objectives, prerequisites, effort, deliverables, evidence, completion criteria and precise resources;
- one to seven stable learning outcome IDs per topic, with the concepts that must be taught;
- `study/integrations.md` using `templates/integrations-plan.md`.

Stable learning outcome IDs use `LO-1`, `LO-2` and so on inside each topic. They are internal traceability keys. The learner-facing objective remains natural prose, but it must describe the same promised results.

The learner must be able to understand the whole path without reading workflow terminology or already knowing the course vocabulary. Translate `materialized` to “aula pronta” and `planned` to “aula futura” in learner-facing prose.

## Dependency graph, not numbered sequence

Topic numbers provide stable identity and roadmap order. They do not establish prerequisites by themselves. Use only direct prerequisite IDs declared in each topic contract.

When the graph branches:

- do not claim numeric adjacency as dependency;
- do not use “todas as etapas anteriores” instead of direct prerequisites;
- write future task copy from the direct prerequisite list;
- explain that readiness follows prerequisites, not card number.

## Personalization

Use intake and diagnostic evidence to personalize why each topic matters, examples, difficulty, prerequisite retrieval, preferred formats, accessibility, practice balance, source selection and next-step language.

Treat subject knowledge and transferable experience as separate dimensions. Adjacent experience may make examples more sophisticated, but it must not remove foundations the learner does not know.

Do not manufacture intimacy or expose unnecessary personal data.

## Beginner-first concept progression

When the configured level is `none` or `beginner`, or diagnostic records missing vocabulary:

1. explain what the object is in plain language before how it works;
2. expand title acronyms at first learner-visible occurrence;
3. define prerequisite terms before using them inside another definition;
4. distinguish neighboring concepts and common confusions;
5. explain why the concept exists and where it appears;
6. provide an intuition bridge;
7. then introduce mechanisms, technical vocabulary, limits and implementation.

Every beginner module must contain:

- `## Começando do zero`;
- `### Vocabulário desta aula`;
- `## Intuição antes dos detalhes`;
- either a bounded analogy or a labeled concrete example before the main technical explanation.

## Writing and example contract

Write one main conceptual move per paragraph. Prefer a plain sentence before the formal name. Avoid stacking undefined terms.

Every ready lesson must include at least one labeled analogy or concrete example. When useful, combine an everyday situation, a domain-relevant worked example and a case with ambiguity, failure or a limit.

A fictional but plausible example is a **realistic teaching scenario**, not a real case. A real event, statistic or result requires a verified source.

## Topic and task granularity

A topic is an independently assessable capability, not a reading or administrative action. Use three to seven focused actions, normally 10–25 minutes each. Prefer topics around 45–90 minutes and split above 120 minutes when responsibly separable.

## Content-generation strategy

For `adaptive_rolling_window`:

1. generate the complete roadmap and every topic contract;
2. generate all detailed content only when the curriculum is within both configured full-upfront thresholds;
3. otherwise materialize only the first deterministic lookahead window;
4. choose it in topological order;
5. keep future contracts `content_status: planned` without broken module, rubric or form links.

For every materialized topic, create:

- a complete module under `study/modules/`;
- a 100-point rubric under `study/assessments/`;
- a GitHub Issue Form under `.github/ISSUE_TEMPLATE/`;
- positive content version and materialization date;
- a current independent review under `state/content-reviews/`.

Do not create flashcards, Markdown decks, TSV exports or Quizlet sets. Retrieval practice must be taught inside the lesson through prerequisite recall, guided questions, independent application and `## Confira sem consultar`.

## Outcome traceability

For every materialized topic:

1. preserve approved learning outcome IDs and required concepts;
2. place exactly one hidden `open-study-path:outcome` marker for each outcome beside content that genuinely teaches it;
3. add `outcome_ids` to every assessment-rubric question;
4. ensure every outcome is taught and assessed at least once;
5. run `instructions/36-review-course-content.md` as a separate pass;
6. create `state/content-reviews/TOPIC-000.yml` for the current version.

A marker or identifier beside a heading does not prove coverage. Reviewers must verify the actual explanation, example, practice and assessment.

## Complete-content contract

Every ready lesson must be self-contained for the configured time and level. It must include:

1. personal orientation and clear outcome;
2. granular study session;
3. first-principles onboarding when required;
4. prerequisite retrieval based on direct prerequisites;
5. actual explanatory content;
6. definitions, relationships, limits and nuance;
7. intuition through a bounded analogy or concrete example;
8. at least one explained Mermaid model;
9. at least two worked examples;
10. common errors and corrections;
11. guided practice with hints;
12. independent practice and deliverable;
13. active recall inside the lesson;
14. direct assessment action;
15. **How this content was built** provenance;
16. **Other ways to learn** when useful;
17. **Sources and paths to deepen** with verified links and locators.

Reject modules that merely instruct the learner to read, study, watch, reflect or discuss without teaching the underlying content.

## Source and provenance contract

For every materialized module:

- inspect every source before including it;
- use three to seven curated sources by default;
- include at least one primary or official source when one exists;
- include at least one reliable explanatory source;
- include a complementary format when it adds real pedagogical value;
- explain how each source was used;
- record chapter, section, page, DOI, version, lesson, exercise or timestamp;
- distinguish sourced claims from agent-created diagrams, analogies, examples and exercises;
- distinguish a realistic teaching scenario from a sourced real case;
- do not cite a plugin response instead of the original document;
- provide a free or official alternative for potentially paid resources;
- keep the lesson understandable without opening external links.

## Videos and courses

Use videos when they provide a useful alternative explanation or demonstration. Include title, creator or institution, direct link, duration or recommended timestamp, language or legends when relevant and one active task.

Use Coursera, edX, Udemy, Khan Academy or other catalogs only at the exact section, lesson or exercise level. Never assign an entire course as one vague task.

## Visual learning with Mermaid

The roadmap must show the actual topic dependency graph. Every materialized module contains the configured number of explained Mermaid diagrams. A diagram is a teaching artifact, not decoration.

## Contextual integration recommendation

Recommend only capabilities supported by concrete current course signals. Explain them in learner language in `study/integrations.md`; keep preflight, authority and state classifications inside technical details and `state/integrations.json`.

Apply contextual defaults:

- Consensus supports empirical research but never replaces original citations;
- Trello is preferred for rich courses; GitHub Issues is the first fallback and Todoist may be a task backend or flexible reminder tool;
- `fixed_calendar` uses one calendar provider for fixed study blocks;
- `flexible_reminders` uses Todoist and no duplicate calendar event;
- `none` and `decide_later` activate neither routine provider;
- missing day, time, duration, recurrence or timezone is collected before activation;
- Gmail remains an on-request action and is not configured during generation or publication;
- Habitify supports consistency only;
- Mermaid remains canonical even with an external visual workspace;
- Google Drive may hold deliverables;
- Airtable remains a `github_to_airtable` projection;
- course and media platforms are resource discovery, not progress authority.

Use harmless reads only for providers needed now. If an optional provider is unavailable, continue with the repository-native alternative.

## Assessments

Each assessment contains five substantial prompts covering understanding, analysis, transfer, misconception correction and evidence. Issue Forms include labels, hidden topic marker and complete prefilled title.

Every rubric question declares one or more valid `outcome_ids`. All approved outcomes must be assessed. For beginner topics, at least one prompt verifies that the learner can define the central object and distinguish it from a nearby concept before applying it.

The lesson may teach:

`Terminei <título da aula>. Avalie minhas respostas.`

Continue accepting:

`Finalizei o TOPIC-000. Avalie minhas respostas.`

The module contains the direct clickable Issue Form URL. Never expose only the YAML filename.

Assessment links and commands inside the lesson do not authorize the generation-completion response to skip publication.

## Roadmap and contracts language

Roadmaps and topic contracts emphasize what the learner will be able to do, why it matters, what is ready, what will be prepared next, how to know the stage is complete and where supporting sources are.

Do not foreground generation thresholds, topological order, PR status, CI or internal classifications in learner-facing sections.

## Pull request and automatic review

Open one draft PR containing only allowed curriculum artifacts. Run curriculum review, course-content review for every materialized topic, and the shared phase review. The lesson, metadata and reviews belong to the same content version and PR. Merge only when no material decision or blocking finding remains.

## Completion

Create no external tasks, events, reminders, email messages, notifications or workspaces during generation. Complete using `instructions/phase-completion.md` and resolve the next action through `scripts/lifecycle_next_action.py`.

When generation succeeds and publication is pending, guide naturally to this as the only normal copyable continuation:

`Organize minha trilha nas ferramentas que escolhemos.`

This remains mandatory when the agent itself suggested `sem publicar tarefas ainda`. Do not present `Terminei <título da aula>. Avalie minhas respostas.` as the next command before publication succeeds.

Continue accepting `Publique as tarefas da trilha nas integrações configuradas.` as an alias.
