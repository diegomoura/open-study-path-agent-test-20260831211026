# Task projection architecture

## Decision

Open Study Path uses a provider-independent projection engine. `state/integrations.json` is authoritative; `state/operations/` contains resumable journals; `study/integrations.md` is a generated learner summary.

## Why

A real Trello/Todoist publication exposed four coupled failures: internal markers leaked into cards, provider ordering became curriculum semantics, external writes could complete without durable state, and later state updates invalidated historical reviews. A textual contract alone could not prevent recurrence.

## State model

The internal model keeps `planned`, `ready`, `in_progress`, `in_assessment`, `review_required` and `completed`. Ordered interfaces split only the visible presentation of `ready` into one **Próxima aula** and zero or more **Disponível em paralelo** items. This avoids provider-specific state inflation.

GitHub Issues keeps one issue per materialized lesson and the compatible `study:ready` label. Primary-versus-parallel remains private projection metadata, so old instances and automations continue to work.

## Persistence

- `state/integrations.json`: current technical truth, resource identities, projection, read-back evidence and sync result.
- `state/operations/<operation-id>.json`: resumable journal with checkpoints, branch/PR identity and write/read counts.
- `study/integrations.md`: simple current learner instructions rendered from state.
- `state/reviews/`: immutable historical decisions; the latest unambiguous approved review owns the current artifact.

## Safety properties

Adapters resolve all matches before writing, block ambiguity, separate visible fields from private metadata, preserve learner-owned content, read back the complete result, and declare success only after validation and durable persistence. Optional reminder failure does not undo the task backend.

## Migration

Version-1 and version-2 states, six-state boards, `Pronto para estudar`, `Em andamento`, `study:ready-primary`, `study:ready-parallel` and known HTML markers are migrated idempotently. Unknown learner content is preserved.
