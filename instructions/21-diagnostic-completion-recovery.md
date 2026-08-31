# Diagnostic completion recovery

Apply this contract to the terminal part of the diagnostic phase.

## No success before durable completion

Do not say `Diagnóstico concluído`, do not present the roadmap-proposal command, and do not claim that the diagnostic was registered unless all of the following are true for the same current pull-request head:

- `.open-study-path/instance.yml` records `status.diagnostic_complete: true`;
- `state/diagnostic-summary.json` exists and validates against its schema;
- exactly one diagnostic review artifact is approved and covers both diagnostic outputs with current fingerprints;
- every required diagnostic review check is `passed`;
- required CI checks for the current head succeeded;
- the pull request was merged into the default branch;
- a final read of the default branch confirms the merged diagnostic state.

A conversational placement conclusion is provisional until these conditions are satisfied. Never describe a provisional conclusion as repository state.

## Deterministic repair

Treat these findings as internal deterministic defects and repair them in the same branch, operation and pull request:

- missing diagnostic review check;
- stale review fingerprint;
- incomplete generated-artifact coverage;
- schema or field-shape mismatch with an unambiguous repair;
- state saying `diagnostic_complete` while the summary or review is absent;
- summary present while the instance marker still says the diagnostic is incomplete.

Re-run the focused validator before the full inherited workflow. Do not ask the learner to restart the diagnostic merely to repair repository metadata.

## Pending validation is not completion

A message such as `aguarda validação`, `a validação está em andamento` or `depois disso, o próximo comando é` is not a terminal result. Repository work does not continue after the assistant response unless an explicit scheduled automation exists.

Do not offer passive waiting as completion. While checks are pending, continue the same operation until a terminal result is available when the interaction and tools permit it. When the environment cannot continue, state plainly that the diagnostic is not yet persisted and do not reveal the next lifecycle command as available.

## Missing diagnostic evidence

If a chat produced a placement conclusion but no repository branch, summary or review exists, do not reconstruct detailed evidence from the conclusion alone. Resume from preserved conversational answers when they are available in the same chat. Otherwise repeat only the minimum bounded questions needed to create an auditable summary.

Never invent question count, evidence, gaps, misconceptions or learner answers.

## Learner-facing result

After successful merge, report the starting depth and the single next command. Before merge, use language such as `A conclusão provisória é...`, never `Diagnóstico concluído`.
