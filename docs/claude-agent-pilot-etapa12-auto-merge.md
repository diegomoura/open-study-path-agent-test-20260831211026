# Etapa 12 — agent-pilot auto-merge (Opcao C)

Status: **implemented**. Frente 1 of the post-Etapa-11 handoff
("Handoff — Auto-merge (Opcao C) + remocao de slides + integracoes off por
padrao"). Frente 2 (remove slides, integrations off by default) shipped
first as Etapas 10-11.

## Why

Running the "Estoicismo" trilha end-to-end (Etapa 9 item 2) gave the first
real, multi-phase sample of the independent reviewer in production:

| Operation | Veredito do revisor | Realidade |
|---|---|---|
| `generate_detailed` | aprovado, zero blocking findings | miss: `study_slides.enabled` ficou inconsistente; só CI determinístico pegou |
| `publish` | 2 blocking findings | 2 falsos positivos — nenhum era bug real; e o revisor não pegou um link morto |
| `evaluate` | 1 blocking finding | achado real, mas raso — pegou o sintoma, não a causa raiz |

Total: 1 achado real (raso) + 2 falsos positivos (bloqueantes) + 2 misses (1
só via CI determinístico, 1 só via investigação manual). Every error the
reviewer made was "block good" (costs time, not risk), never "approve bad" —
`{reviewer + CI}` never let a broken artifact through in this sample, even
when the reviewer itself was wrong. That is the basis for Opcao C: auto-merge
on `approved + CI green`, plus a cheap, deterministic, non-blocking digest so
a human still sees every merge without being the bottleneck for it.

## What actually changed

### The decision rule

The workflow (`.github/workflows/agent-pilot-setup.yml`) auto-merges
(squash + delete branch) exactly when, for the pull request's final head
(the commit the reviewer job pushed, which includes the review artifact and
usage log):

1. `state/reviews/agent-pilot-<phase>.yml` is genuinely approved. "Genuinely"
   reuses `scripts/review_framework.py`'s `validate_review_document` — the
   same fingerprint/coverage/required-checklist validation the older
   instructions-driven pipeline already requires for a human merge, not a
   bare string comparison against `status: approved`.
2. Every completion check `instructions/manifest.yml`'s
   `automatic_completion.check_sets` declares for that phase succeeded.

If either condition fails, nothing changes from before Etapa 12: the pull
request is left open for a human.

### The CI problem this design had to solve (not anticipated by the handoff)

The handoff assumed "CI verde" could mean waiting on the same check runs the
older pipeline already polls for. That assumption does not hold here:
`agent-pilot-setup.yml` always opens its pull request using the workflow's
default `GITHUB_TOKEN`, and GitHub does not cascade events caused by that
token into new workflow runs. A `pull_request`-triggered workflow like
`validate-template.yml` or `validate-intake-completion.yml` therefore never
starts on its own for this PR — the same restriction already discovered and
documented earlier in this project for `workflow_dispatch` (see
`docs/claude-agent-pilot-etapa9d-diagnostic-answer-form.md`, which solved an
analogous problem for the diagnostic-answer bridge by switching from
`workflow_dispatch` to `workflow_call`).

The fix here is the same technique: every workflow named in
`automatic_completion.check_sets` (`validate-template.yml`,
`validate-curriculum-state.yml`, `validate-intake-completion.yml`,
`validate-diagnostic-completion.yml`, `validate-proposal-completion.yml`,
`validate-usable-generation.yml`, `validate-task-projection.yml` — the last
one already had `workflow_dispatch`, none had `workflow_call`) now also
accepts `workflow_call`, with an optional `ref` input (`validate-template.yml`
additionally keeps its existing `review_base_sha` input). Every checkout step
in those workflows now checks out `${{ inputs.ref || github.ref }}` instead of
the implicit default — without this, a reusable-workflow call would validate
whatever ref originally triggered `agent-pilot-setup.yml` (typically the
default branch), never the new branch the author/reviewer jobs actually
pushed.

`agent-pilot-setup.yml` calls these inline, as jobs, right after `reviewer`:

- `ci-baseline-template`, `ci-baseline-curriculum` — unconditional; every
  phase's `completion_check_sets` includes `baseline`
  (`scripts/test_resolve_completion_check_sets.py` asserts this stays true).
- `ci-intake`, `ci-diagnostic`, `ci-proposal`, `ci-usable-generation`,
  `ci-task-projection` — conditional on a new `resolve-checks` job, which
  runs `scripts/resolve_completion_check_sets.py --phase "$PHASE"` and emits
  one `needs_<check>` boolean per optional check via `GITHUB_OUTPUT`.

This means CI, for the purposes of this gate, is not "did some external run
eventually go green" but "did the exact same validation the branch would
have to pass anyway, run synchronously as part of this workflow, against the
exact commit about to be merged" — arguably a tighter guarantee than polling
external checks, since there is no window where the branch could move
between the check running and the merge happening.

### The decision and digest scripts

- `scripts/resolve_completion_check_sets.py` — pure `required_workflow_names`/
  `required_job_ids`, reusing `instructions/manifest.yml`'s
  `automatic_completion.check_sets` and each phase's (or `generate`
  suboperation's) `completion_check_sets`. Raises `KeyError` for an
  unrecognized phase or an unrecognized required check name — an unknown
  requirement must block loudly, never be silently treated as satisfied.
- `scripts/agent_pilot_merge_decision.py` — pure `decide_merge`: validates
  the review document, then requires every job id in `required_job_ids` to
  have result `"success"`. A required check that only "skipped" (e.g. an
  infrastructure hiccup, or a bug in `resolve-checks` itself) blocks exactly
  like a failure — it is never treated as equivalent to a check that was
  correctly not required for this phase in the first place. Jobs outside
  `required_job_ids` are ignored regardless of their own result.
- `scripts/agent_pilot_merge_digest.py` — pure `build_digest` +
  `parse_source_issue_number` + `load_latest_usage_record`. Per the
  handoff's explicit design requirement, this **never calls the Anthropic
  API**: every field comes from files the author/reviewer run already wrote
  — `state/reviews/agent-pilot-<phase>.yml` (findings, artifacts),
  `state/agent-pilot-usage.jsonl` (real cost/tokens for this run), and
  `state/intake-summary.json.source_reference` (the originating issue).

### The originating-issue field already existed

The handoff asked me to check whether an originating-issue field already
existed before adding one. It does:
`state/intake-summary.json.source_reference`, format
`github_issue:<owner>/<repo>#<number>`, written during `intake`
(`scripts/agent_runtime.py`, `instructions/10-intake.md`). No new tracking
field was added anywhere. `parse_source_issue_number` only trusts a
`source_reference` whose repo matches the current `target_repo` exactly, and
returns `None` (never raises) for a missing, malformed, or cross-repo value
— an instance that never went through GitHub-Issues intake, or whose intake
summary predates this field, still gets a normal auto-merge; the digest is
just logged in the job output instead of posted anywhere, per the "Post the
digest" step's fallback.

### `instructions/03-await-ci-and-merge.md` was deliberately not touched

The handoff guessed this file "provavelmente já descreve políticas de
auto-merge que nunca foram ativadas nesse pipeline específico" and asked to
activate them. That guess does not hold up against the actual file: it is
the fully-implemented automatic-completion contract for the **other**
pipeline — the instructions-driven one, executed by a human or agent reading
`instructions/*.md` directly and using `scripts/ci_completion_state.py`'s
state machine with `workflow.*_merge_policy` (`auto_when_unambiguous` /
`agent_review_then_merge`). `docs/claude-agent-pilot.md` already said as much
before this etapa ("this pilot's automatic-merge policies are not invoked
from this workflow") — that statement was correct, and remains true after
Etapa 12 in the sense that `agent-pilot-setup.yml` still does not read
`workflow.*_merge_policy` or call `ci_completion_state.py`; it has its own,
narrower decision rule, described above. Editing
`03-await-ci-and-merge.md` would have been changing the wrong pipeline's
contract.

## Validation

Every dispatch-free: `scripts/validate_template.py all`, every
`scripts/test_*.py` (including the three new ones), `python -m unittest
discover tests/`. All green locally before opening the PR. No real Anthropic
API dispatch was needed — the decision/digest logic is pure and covered by
fixtures; the CI-checks logic is exercised through the actual reusable
workflows (`workflow_call`) themselves once merged, not simulated.

## Known follow-ups (not in this etapa's scope)

- Item 4's other unblocked piece (fork/label trigger for the pilot) is
  separate work, deferred.
- If a phase's `completion_check_sets` in `instructions/manifest.yml` ever
  grows a check name this workflow does not yet run inline,
  `resolve_completion_check_sets.required_job_ids` raises `KeyError` and the
  `resolve-checks` job fails loudly — by design, but it does mean a manifest
  change and this workflow's job list must be kept in sync by hand; nothing
  currently guards against merging a manifest change alone without the
  matching workflow job.
