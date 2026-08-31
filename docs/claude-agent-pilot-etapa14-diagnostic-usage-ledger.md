# Etapa 14 — README staleness + diagnostic usage ledger gap

Status: **implemented**. Two previously-documented-but-uncorrected findings,
closed while auditing the template for anything else worth fixing before
starting a fresh instance.

## Finding 1 — README.md still advertised flashcards/Quizlet

`docs/claude-agent-pilot-etapa11-integrations-off-by-default.md` had already
flagged this as a known gap ("README.md lista 'Flashcards | Quizlet' como
ativo, mas docs/integration-capabilities.md diz que flashcards foram
removidos") without fixing it. Checked ground truth before touching
anything:

- `instructions/30-generate-path.md`, `templates/module.md`, and
  `scripts/validate_learning_experience.py` all confirm flashcards were
  genuinely removed (PR #61, "Simplify study integrations and routine
  setup") -- `validate_learning_experience.py` actively **fails** CI if a
  materialized module retains `study/flashcards/` or `flashcards_study`.
  `docs/integration-capabilities.md`'s "Removed practice integrations"
  section is correct.
- `README.md` was the stale side: it still listed "flashcards quando
  ajudam" in the feature bullets, "Quizlet" in the integrations prose, a
  `study/flashcards/` line in the repo-structure section, and a
  `| Flashcards | Quizlet | Markdown e TSV |` row in the integrations
  table.

Fixed: removed all four stale mentions from `README.md`. No code changed --
this was a documentation-only correction once the ground truth was
confirmed.

## Finding 2 — diagnostic's non-terminal turns were never logged

Documented in memory as a known ledger gap without a design yet: "A known
ledger gap exists: diagnostic's pre-terminal turns are not recorded in
state/agent-pilot-usage.jsonl."

Root cause, confirmed by reading `.github/workflows/agent-pilot-diagnostic.yml`
directly: unlike every other agent-pilot phase (one `workflow_dispatch` = one
complete author+reviewer operation), `diagnostic` runs once per learner
reply. Only the **terminal** turn (once the whole diagnostic form has been
answered and evaluated) runs a `reviewer` job at all -- and
`scripts/summarize_agent_pilot_usage.py --append-log
state/agent-pilot-usage.jsonl` was only ever called from that reviewer job.
Turn 1's "Run author agent" step is a real, billed Anthropic API call (it
posts the question batch) -- its `usage` was uploaded as a
`author-result.json` workflow artifact, but never reached the persistent
ledger a course creator actually reads later to answer "how much did this
cost." For any diagnostic session with more than one turn, the ledger
silently under-reported the session's real cost.

### The fix

1. `scripts/summarize_agent_pilot_usage.py`'s `combine()` now accepts
   `reviewer_result=None` for an author-only record, and the CLI's
   `--reviewer-result` is now optional. An author-only record has no
   `"reviewer"` key at all (rather than a hollow `{"model": None}`), so
   reading the ledger later can tell an author-only turn apart from a
   real combined author+reviewer operation at a glance.
2. `.github/workflows/agent-pilot-diagnostic.yml`'s `author` job gained one
   new step, `Log this turn's usage (non-terminal turn -- author-only, no
   reviewer)`, gated on `steps.diff.outputs.completed == 'false'` -- so it
   runs strictly *after* the existing diff check that decides whether this
   turn was terminal, and can never itself flip that decision by adding a
   file to the working tree before the check runs. It appends the turn's
   real usage to `state/agent-pilot-usage.jsonl` and pushes that one commit
   directly to the repository's default branch (`github.ref_name`) -- not
   the throwaway per-turn feature branch, which only ever exists to hold
   the *terminal* turn's own commit before its pull request, and which a
   non-terminal turn has nothing else to attach a ledger-only commit to.

The terminal turn's own logging (in the `reviewer` job, unchanged) still
records that turn's combined author+reviewer usage exactly as before -- this
fix only adds the previously-missing lines for every turn before it.

### What this does not fix (documented, not in scope here)

- The post-merge digest (`scripts/agent_pilot_merge_digest.py`,
  `load_latest_usage_record`) reads only the *latest* ledger line matching a
  phase. For `diagnostic`, that is fine today -- `agent-pilot-diagnostic.yml`
  does not use the Etapa 12 auto-merge gate at all (it is a separate
  workflow file from `agent-pilot-setup.yml`; the terminal turn still opens
  a plain pull request for a human to merge), so the digest is never
  actually invoked for this phase yet. If diagnostic is ever wired into
  auto-merge, `load_latest_usage_record` would need to *sum* every turn's
  ledger line for that session rather than take the last one, to report the
  session's true total cost -- left as a follow-up for whenever that wiring
  happens, not invented speculatively here.
- The race between this new direct-to-default-branch push and any
  concurrent write to the same branch (e.g. two diagnostic sessions running
  in parallel across different issues in the same instance) is not
  specially handled -- a non-fast-forward push simply fails the step
  loudly, which is an acceptable, visible failure mode for a low-stakes
  ledger append, not a silent one.

## Validation

`scripts/validate_template.py all`, every `scripts/test_*.py` (including the
new `test_summarize_agent_pilot_usage.py`), `python -m unittest discover
tests/`. All green locally. No Anthropic API dispatch needed for either
finding -- the README fix is prose, and the ledger fix is exercised entirely
through `combine()`'s unit tests and a subprocess-level CLI test, not a real
diagnostic dispatch.
