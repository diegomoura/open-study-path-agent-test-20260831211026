# Canonical task-backend projection

This contract is the single provider-independent model used by publication, progress tracking, assessment projection and migration. Provider adapters translate the model; they do not define curriculum semantics.

## Projection record

Represent every projected lesson with:

- `topic_id`;
- learner-visible lesson number and title;
- direct prerequisite IDs;
- content version;
- stable internal canonical state;
- expected learner-visible state and visual position;
- learner-visible managed fields;
- external ID and URL when available;
- managed-fields version;
- roadmap fingerprint;
- sync status and last-sync time.

Generate learner-visible fields independently from internal metadata. Store synchronization metadata only in `state/integrations.json`, the operation journal, or a genuinely private provider field. Never use HTML comments, hidden-looking prose or learner-visible comments as metadata storage.

## Internal and visible states

Internal states remain provider-independent:

- `planned`;
- `ready`;
- `in_progress`;
- `in_assessment`;
- `review_required`;
- `completed`.

Ordered backends use exactly:

`Planejado → Disponível em paralelo → Próxima aula → Em estudo → Em avaliação → Revisão necessária → Concluído`

`ready` is one internal state with two visible roles. When at least one unfinished eligible materialized lesson exists, exactly one—the earliest in approved roadmap order—is **Próxima aula**. Other unfinished eligible materialized lessons are **Disponível em paralelo**. Eligibility comes only from direct prerequisites and durable progress. The learner manually moves only an available lesson to **Em estudo**.

The permanent orientation resource `📌 Leia antes de começar` stays first in **Planejado** and is never counted as a roadmap lesson.

## Provider compatibility

### Trello and Todoist

Create or reuse only managed lists or sections, in the exact canonical order. Preserve learner-created lists, cards, tasks, comments, attachments and unknown fields. Reorder managed lists without moving unmanaged lists destructively.

### GitHub Issues

Keep the established compatibility contract: one issue per materialized lesson and one managed execution label. Both primary and parallel ready lessons use `study:ready`; their role remains in internal projection metadata. Continue accepting and migrating `study:ready-primary` and `study:ready-parallel` to `study:ready`. Do not project all future roadmap topics as issues unless a separate architectural decision, schema migration and regressions explicitly authorize that change.

## Visible-content boundary

Validate every managed learner-visible field before writing and after read-back, including title, description, checklist items and managed comments. Fail publication when a managed field contains:

- `<!--`;
- `open-study-path` used as a machine marker;
- an internal `TOPIC-000` identifier;
- `content_version`;
- serialized prerequisite arrays;
- fingerprints or SHA-256 payloads;
- provider IDs;
- synchronization JSON or operation payloads.

The executable validator in `scripts/task_projection_engine.py` is authoritative. Text in this Markdown file is not sufficient evidence.

## Matching and idempotency

Before the first write, resolve every managed resource in this order:

1. durable external ID;
2. private stable key;
3. exactly one compatible visible-title match.

An ambiguous match blocks all destructive writes. A rerun of an unchanged operation creates no duplicate and performs no external write. Preserve the same `operation_id` during recovery.

## Read-back before success

After all required external writes:

1. read the complete board, project or issue set;
2. normalize provider data;
3. verify lesson count and unique `topic_id` values;
4. verify managed list order when supported;
5. verify exactly one primary next lesson when eligible;
6. verify all parallel eligible lessons;
7. verify prerequisites, states and roadmap fingerprint;
8. scan every managed visible field for internal metadata;
9. verify current lesson, practice and assessment URLs;
10. persist the operation checkpoint and `state/integrations.json`;
11. render `study/integrations.md` from authoritative state;
12. only then report success.

A reminder failure is optional and must not roll back a valid task-board publication. Record it as an optional warning.

## Durable operation contract

`state/integrations.json` is the complete authoritative integration state. `state/operations/<operation-id>.json` is a valid, revisable, resumable technical journal for publication, evaluation and progress projection. It is validated by the dedicated operation schema and task-projection gate. Phase review covers the semantic state and learner summary; it does not reject a valid operation journal as out of scope.

The journal records at least operation identity, provider, status, attempt, checkpoints, reads, writes, roadmap fingerprint, branch, pull request, commit budget and timestamps. One operation maps to one convergent branch and one pull request.

## Historical reviews

Historical reviews remain immutable evidence of the artifact observed at that time. A later approved review may supersede ownership of the current artifact. Validators resolve the latest unambiguous approved owner by `reviewed_at`; they never rewrite historical fingerprints merely because publication later changes `state/integrations.json` or `study/integrations.md`.

## Migration

Migration is idempotent. Reuse the current container, create or reorder only managed states, preserve learner-owned resources, normalize `Pronto para estudar`, `Em andamento`, six-state layouts, `study:ready`, version-1 integration state and known legacy markers. Remove only known `open-study-path` markers from managed fields. Preserve unknown content. Persist version-3 state only after successful read-back.

## Branch convergence

Build and validate the complete local or temporary tree before opening the PR. Use one logical commit per operation, or deterministically rebuild/squash the same operation branch before opening or updating the same PR. Check the commit budget before PR creation, keep the same `operation_id`, and never create several recovery branches manually.
