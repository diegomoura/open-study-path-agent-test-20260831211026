# Propose and approve the learning path architecture

Use this suboperation after intake and diagnostic are complete and before detailed curriculum generation.

The proposal creates the complete learner-facing roadmap architecture only. It does not materialize detailed lessons, assessments, flashcards or external tasks.

## Request interpretation

Treat these requests as equivalent to this suboperation:

- `Gere uma proposta de trilha com base no intake e no diagnóstico. Abra um pull request e não publique tarefas ainda.`
- `Proponha minha trilha de estudos.`
- `Monte o roadmap da minha trilha.`

The wording `proposta` means a candidate architecture authored in a draft pull request and independently reviewed by the agent. It does not create an implicit learner-approval gate.

`Abra um pull request` describes the audit mechanism. It does not mean `deixe o PR aberto`, `aguarde minha revisão` or `não faça merge`.

`Não publique tarefas ainda` defers only the later `publish` phase. It does not block review, correction, validation, readiness transition or merge of the proposal.

Only an explicit instruction such as `deixe o PR aberto`, `espere minha revisão`, `não faça merge` or an unresolved material decision may stop before merge.

## Inputs

Read:

- approved `study.config.yml`;
- `state/intake-summary.json`;
- `state/diagnostic-summary.json`;
- `.open-study-path/instance.yml`;
- `docs/learner-facing-language.md`;
- `docs/beginner-first-pedagogy.md`;
- `instructions/35-review-curriculum.md`;
- `instructions/04-review-generated-artifacts.md`.

## Outputs

Create one coherent proposal containing only:

- `study/roadmap.md` with the complete topic graph, direct prerequisites, effort estimates, intended evidence and final outcome;
- `.open-study-path/instance.yml` with the proposal state;
- one current curriculum review under `state/reviews/`.

Do not create `study/topics/`, modules, rubrics, assessment forms, flashcards or integration projections during this suboperation.

## Proposal quality

The roadmap must:

- preserve the complete approved learning request;
- use diagnostic evidence without treating adjacent professional experience as subject mastery;
- define coherent independently assessable capabilities;
- use direct prerequisites rather than numeric sequence;
- include every requested mastery area or explain a justified consolidation;
- estimate effort honestly without forcing the content into an arbitrary deadline;
- identify the final deliverable and the evidence expected from each capability;
- use learner-facing language and define unfamiliar terms at first occurrence;
- contain no placeholder graph or template residue.

## Automatic review and state transition

After authoring:

1. run `instructions/35-review-curriculum.md` as a separate curriculum-architecture pass;
2. correct every resolvable blocking finding;
3. run `instructions/04-review-generated-artifacts.md` with the `curriculum` profile;
4. record exact SHA-256 fingerprints for the roadmap and instance marker;
5. set these values atomically on the final reviewed head:

```yaml
status:
  curriculum_proposed: true
  curriculum_approved: true
  curriculum_generated: false
```

Never end an approved proposal with `curriculum_approved: false`.

## Pull request and merge

Open the pull request as draft while authoring and reviewing. Under `workflow.curriculum_merge_policy: agent_review_then_merge`, complete the operation only when:

- the proposal review is approved;
- every changed generated artifact is covered by current fingerprints;
- all required checks for the unchanged head pass;
- the pull request is mergeable;
- no explicit no-merge request or unresolved material decision exists.

After the final reviewed push, run `instructions/03-await-ci-and-merge.md` and follow `scripts/ci_completion_state.py` exactly:

1. capture the final head;
2. mark the pull request ready;
3. enable auto-merge when supported;
4. observe the required checks for that exact head;
5. merge with the validated head as the atomic precondition;
6. verify the persisted proposal state on the default branch.

Do not end the learner interaction merely because CI is still running. Do not provide the next command before the state machine reaches `complete`.

Do not ask the learner to review the whole pull request merely because it exists. A human decision is required only for a concrete ambiguity that changes scope, prerequisites, effort or the intended final outcome.

## Completion

After merge, explain briefly that the roadmap architecture is approved and that no tasks or external resources were published.

Use this as the next copyable command:

`Crie minha trilha de estudos.`

That next suboperation creates every topic contract and the configured initial window of complete lessons, assessments and local practice before publication.