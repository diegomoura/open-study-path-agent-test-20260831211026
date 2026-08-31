# Diagnostic

Run this phase only after intake has been imported and validated.

The diagnostic is a placement step, not a lesson, interview marathon or exhaustive exam. Its only purpose is to collect enough evidence to choose a responsible starting depth.

## Use existing evidence first

Before asking anything, read the intake, prior evidence and any existing diagnostic summary. Do not ask for facts that are already reliable. Cover only the dimensions still needed for placement:

- prior exposure and retention;
- conceptual understanding;
- practical application;
- one likely misconception or boundary case.

Do not test every possible curriculum topic. Remaining gaps belong in the learning path.

## Question budget

For a learner declared as `none` or `beginner`:

- target 3 to 5 questions;
- hard maximum of 7 questions.

For a learner declared as `intermediate` or `advanced`:

- target 4 to 7 questions;
- hard maximum of 10 questions.

Exceed the hard maximum only when the owner explicitly requests a comprehensive assessment. Record `owner_requested_comprehensive` in the diagnostic summary. Never continue merely because more questions could produce more detail.

Choose the number of questions once, in the first turn, from this budget -- do not decide question-by-question as answers arrive, since there is no second round to react to them.

## Interaction style (single-form batch)

Real dispatch finding (Etapa 9 item 2): the original one-question-at-a-time design, while genuinely adaptive, cost roughly four times a normal phase in a real session (~$0.48 for one placement, against ~$0.11-0.12 for bootstrap/configure_intake/intake) and took several `issue_comment` round trips to complete -- each turn re-reconstructs the entire thread from scratch (`scripts/build_diagnostic_context.py`), so cost and latency both grow with every question instead of staying flat. This phase now asks its whole question set in one turn and evaluates everything in the next, cutting a placement down to exactly two turns (occasionally one, see below) regardless of how many questions the budget calls for.

- **Turn 1:** read the intake and any existing evidence, choose the question count for this budget tier, and post all questions together as a single numbered list in one comment. State the total count up front (e.g. "5 perguntas curtas"). Include a direct link to the reusable diagnostic-answer form (`.github/ISSUE_TEMPLATE/diagnostic-answer.yml`, pre-filled with this session's issue number) as an alternative to typing a comment by hand -- either channel produces the same plain comment on this issue by the time the next turn reads it. Do not wait for or request answers one at a time.
- **Turn 2:** the learner's reply is expected to answer every question in one message, in any order or format. Evaluate the whole reply at once against every question and finish the phase -- write the summary, run the review, and complete. This is always the terminal turn; there is no third round.
- **Optimization, not a requirement:** if the very first message already contains complete, unprompted answers to what the question set would have asked (e.g. the owner pastes a full self-assessment upfront), skip straight to evaluation and finish in turn 1. Do not manufacture a question round just to have one.
- If the single reply leaves a genuine gap on one dimension, do not open a second round of questions to close it. Record `evidence_sufficiency: limited`, note the specific gap in `material_caveats`, and choose a conservative starting depth instead -- exactly the existing hard-maximum fallback below, just reached after one round instead of several.
- Do not praise, restate or grade individual answers before concluding. Avoid mini-lessons; correct a misconception only when the correction is needed to continue, in at most two short sentences, as part of the completion response.
- Do not send a separate transition message such as "there is enough evidence; I will register it". Once the single reply is evaluated, perform the repository operation and send only the guided completion response.
- Do not generate the curriculum during this phase.

Record which method produced this summary in `method` (e.g. `"single_form_batch"`), so a future real-dispatch cost comparison can tell which sessions used which interaction style.

## Stopping rule

The single combined reply is always sufficient to stop -- there is no further round to extend the session. Evaluate what the reply actually supports:

1. if a starting depth can be selected with responsible confidence, record `evidence_sufficiency: sufficient`;
2. if at least one conceptual and one applied signal are available (or reliable prior evidence already covers one of them) but some secondary dimension is thin, that thinness is a caveat, not a reason to ask again;
3. if the reply is genuinely too sparse to place responsibly on more than one dimension, choose the most conservative starting depth the evidence does support and record `evidence_sufficiency: limited`, exactly as the old hard-maximum fallback did.

Repeated or redundant detail in the single reply does not change the conclusion once the dimensions above are covered.

## Output

Create `state/diagnostic-summary.json` from `templates/state/diagnostic-summary.json` and validate it against `schemas/diagnostic-summary.schema.json`.

Record:

- question count and budget;
- evidence sufficiency;
- confirmed competencies;
- knowledge gaps;
- misconceptions only when actually observed;
- required prerequisites;
- recommended starting depth;
- material caveats.

Do not persist the raw transcript, unnecessary personal details or conversational filler. Update `.open-study-path/instance.yml` with `status.diagnostic_complete: true`.

## Independent diagnostic review

After the authoring pass, run `instructions/04-review-generated-artifacts.md` with the `diagnostic` profile.

The diagnostic reviewer must reconstruct each placement conclusion from the bounded evidence recorded in the summary. It must verify that:

- the starting depth is supported rather than guessed;
- transferable experience was not treated as subject mastery;
- observed gaps and misconceptions were not invented;
- the question budget and stopping rule were respected;
- raw answers and unnecessary personal data were not persisted;
- the next phase is generation, not additional teaching disguised as diagnosis.

Store the review separately under `state/reviews/<diagnostic-operation>.yml`. The manifest keeps this in `review_outputs`; it is audit evidence rather than a diagnostic-domain output.

## Diagnostic pull-request policy

Read `workflow.diagnostic_merge_policy` from `.open-study-path/instance.yml`. If it is missing, use `manual`.

The diagnostic domain output may change only:

- `.open-study-path/instance.yml`;
- `state/diagnostic-summary.json`.

The pull request also includes exactly one diagnostic review artifact under `state/reviews/`. No other generated path is allowed.

For `auto_when_unambiguous`, self-review the diff and merge after required checks pass only when:

- the diagnostic summary validates;
- the question budget was respected or has an allowed explicit exception;
- the domain diff contains only the two files above;
- the diagnostic review covers both current files with exact SHA-256 fingerprints;
- every diagnostic review check passed and no blocking finding remains;
- no raw transcript or unnecessary personal data was persisted;
- the starting depth is supported by the recorded evidence;
- no unresolved contradiction requires owner review.

Do not attempt to formally approve a PR authored by the same account. Verification against the phase contract, the separate diagnostic reviewer pass and successful CI constitute the automated review before merge.

## Completion

Follow `instructions/phase-completion.md`. By default, report only the starting depth, artifact link, merge state and next command. Do not list all competencies and gaps in chat unless the owner asks for an audit.

Guide the owner to the roadmap-proposal suboperation with:

`Gere uma proposta de trilha com base no intake e no diagnóstico. Abra um pull request e não publique tarefas ainda.`

This wording is authored by the system itself. It authorizes the normal proposal workflow: create a draft as a temporary work area, run the independent curriculum review, correct findings, validate, mark ready and merge under `agent_review_then_merge`. It does not ask the learner to review the pull request and does not request that it remain open. `Não publique tarefas ainda` restricts only the later publication operation.
