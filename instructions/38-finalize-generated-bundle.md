# Finalize a generated learning bundle

Use this contract whenever a phase creates or changes a materialized lesson. It applies to initial generation and later rolling materialization.

## One final source state

Finish the learner-facing lesson, assessment form, rubric, flashcards and practice sections before the module is considered final. Do not treat an intermediate lesson as final while still editing it.

A published lesson contains no YAML frontmatter. Operational metadata remains in `study/topics/TOPIC-000.md`.

Use the canonical lesson headings and order from `scripts/generated_instance_contract.py`. `## Pratique e revise` and `## Outras formas de aprender` are separate sections and must both remain present.

## Semantic assessment validation

Validate assessment commands from parsed YAML values, not from raw serialized lines. YAML wrapping, quoting or block-scalar style must not invalidate a command whose semantic text is unchanged.

A URL or DOI is a valid precise source locator. Page, section, chapter, exercise and timestamp locators remain valid where a direct address is unavailable.

## Atomic dependent regeneration

After the final lesson text is settled:

1. synchronize the bounded practice-link block;
2. validate the module and assessment form;
3. run the independent content review;
4. refresh specialized review fingerprints;
5. refresh the generic phase review fingerprints last;
6. run the complete repository validation before the first or next push.

When a lesson changes, use `regeneration_targets()` from `scripts/generated_instance_contract.py` to identify the dependent specialized reviews that must be refreshed in the same final batch.

Never fix one stale artifact, push it, wait for validation to reveal the next dependent stale artifact and repeat. Prepare and validate the complete closure locally, then publish one coherent head.

## Review separation

`state/content-reviews/` is specialized review evidence. It is validated by its own contract and is not itself a generated artifact that requires approval by a second generic review. The generic phase review covers the lesson, topic contract, assessment and flashcards.

## Observable branch updates

Do not rely on an automation-authored commit to trigger another automatic validation cycle unless that behavior has been explicitly verified for the repository.

Prefer an agent or connector commit for the final validated head. A self-updating workflow is allowed only when its resulting head is observable and the normal required checks are demonstrably created for that exact SHA.

Remove temporary recovery scripts and workflows before the final validation. They must not be part of the merged study repository.
