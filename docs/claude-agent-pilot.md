# Agent pilot: real API calls for one setup phase

Stage 2 of the multi-agent work proposal (see the proposal document shared
outside this repository, section 7, step 2). Stage 1
(`docs/agent-model-configuration.md`) was pure model-selection logic with no
API calls. This is the first workflow that actually sends a request to the
Anthropic API and acts on what comes back.

## Scope

Six manifest phases (four full phases plus two suboperations of `generate`)
wired to a real agent call so far:

- `bootstrap_instance`, `configure_intake` -- stage 2/Etapa 3, allowed diff
  small and mechanical (`instructions/02-setup-execution.md`, "Allowed setup
  diff"). Validated with real dispatches; see
  `docs/claude-agent-pilot-etapa3.md`.
- `intake` -- Etapa 4 (proposal, section 7, step 4). Validated with 3 real
  dispatches (unique and ambiguous cases); see
  `docs/claude-agent-pilot-etapa4.md`, sections 1-5.
- `publish`, restricted to the `task manager: GitHub Issues` backend only.
  Validated with 2 real dispatches -- real issue creation, idempotent
  reuse, and correct blocking on invalid visible content all confirmed;
  no clean `success` case yet (the validation dispatch hit a naming
  collision between the disposable test repository's own name and the
  visible-content validator -- see `docs/claude-agent-pilot-etapa4.md`,
  section 6.5). Trello/Todoist/Notion remain deferred until the owner
  decides to pick integrations back up; each needs its own Secret and its
  own adapter, and the work proposal's section 6 (key security) only ever
  addressed `ANTHROPIC_API_KEY`, not third-party provider Secrets.
- `generate_proposal` -- the `proposal` suboperation of manifest.yml's
  `generate` phase only (`instructions/28-propose-path.md`, roadmap
  architecture -- no materialized content). Etapa 5's first slice
  (proposal, section 7, step 5). Validated with 1 real dispatch (Opus) --
  see `docs/claude-agent-pilot-etapa5.md`, section 6.
- `generate_detailed` -- the `detailed_generation` suboperation
  (`instructions/30-generate-path.md` -- topic contracts, lesson modules,
  rubrics, GitHub Issue Forms). Etapa 5's second
  slice (Etapa 5b). Validated with 7 real dispatches -- real pedagogical
  content generation and correct reviewer blocking on a real gap both
  confirmed, no clean `approved` run yet (the last attempt correctly
  blocked on a missing required deliverable, `state/content-reviews/`,
  now fixed in the prompt but not re-validated) -- see
  `docs/claude-agent-pilot-etapa5.md`, section 8. Study slides were later
  removed from the pilot entirely (not just toggled off) -- see
  `docs/claude-agent-pilot-etapa10-remove-slides.md`.

`diagnostic` (Etapa 4b) has its own workflow now
(`.github/workflows/agent-pilot-diagnostic.yml`), triggered by
`issue_comment` per learner answer instead of `workflow_dispatch` one-shot,
since `instructions/20-diagnostic.md` requires a real, multi-turn
interactive placement session with the learner, which does not fit this
harness's other phases' one-shot `run_agent()` -> `finish_phase()` shape.
Originally one question per turn; Etapa 9c (real dispatch measured this at
~4x a normal phase's cost) switched the question-asking style to a single
form batch -- see `docs/claude-agent-pilot-etapa9c-diagnostic-single-form.md`.
Etapa 9d added a real Issue Form (`.github/ISSUE_TEMPLATE/diagnostic-answer.yml`)
as an alternative to typing the reply as a raw comment, bridged back to the
session issue by a small deterministic, zero-LLM-cost workflow -- see
`docs/claude-agent-pilot-etapa9d-diagnostic-answer-form.md`.
The workflow's trigger and turn/terminal mechanics are unchanged from the
original real 4-turn validation (question budget respected, correct
placement conclusion, reviewer approved with substantive findings) --
see `docs/claude-agent-pilot-etapa4b-diagnostic-design.md`, section 6.

`generate` (curriculum/content) has not been picked up either --
proposal section 7, step 5. `publish`'s real-dispatch validation is
constrained by this: there is no real approved roadmap in the disposable
test repository yet, so its validation dispatch uses a small fixture topic
list passed through `extra_context` rather than a real curriculum.

`configure_intake` in this pilot always resolves as if the owner already
selected the `github_issue` provider. The instruction file
(`instructions/05-configure-intake.md`) still describes an interactive
owner choice among three providers for whenever a future stage adds a
`workflow_dispatch` input for provider selection, but an unattended run has
no one to ask, so the author prompt defaults to the recommended option
instead. Jotform and manual YAML intake are currently unreachable: the
manual chat path that used to run them was removed entirely (Etapa 8), and
no dispatched phase wires either one yet. `intake` (Etapa 4) inherits the
same restriction: only the `github_issue` provider path is wired to a real
agent call.

## Files

- `scripts/agent_runtime.py` -- the harness. Two tool sets: authors get
  `read_file` / `list_dir` / `write_file` / `finish_phase`; reviewers get
  `read_file` / `list_dir` / `submit_review`. Every `write_file` call is
  checked against a hard-coded allowlist mirroring
  `instructions/02-setup-execution.md` *before* touching disk -- the model
  cannot write outside it no matter what it asks for. This is a deliberate
  extra guardrail beyond the CI validators: those catch a bad diff after the
  fact, this stops one from being written at all.
- `scripts/build_agent_prompt.py` -- assembles the system/user prompt from
  the real instruction files (`AGENTS.md`, `instructions/00-bootstrap.md` or
  `instructions/05-configure-intake.md`, `instructions/02-setup-execution.md`,
  `instructions/phase-completion.md` for the author;
  `instructions/04-review-generated-artifacts.md` and
  `docs/review-framework.md` for the reviewer). It reads these files at
  workflow run time rather than duplicating their text, so this stays the
  single source of truth for every phase's contract (the manual chat path it
  once had to stay in sync with was removed entirely in Etapa 8).
- `scripts/summarize_agent_pilot_usage.py` -- combines the author's and
  reviewer's token usage/cost into one record, appended to
  `state/agent-pilot-usage.jsonl` in the target repository.
- `scripts/format_pr_body.py` -- renders the pull request body (status +
  usage estimate) as a small standalone script, specifically so the workflow
  YAML never embeds a multi-line Python string inside a `run:` block --
  that pattern is what caused two of the YAML bugs during this pilot's first
  real dispatches.
- `.github/workflows/agent-pilot-setup.yml` -- `workflow_dispatch` only. Two
  sequential jobs, `author` then `reviewer`, each its own `run_agent()` call
  with its own fresh message history. The reviewer job never receives the
  author job's transcript or reasoning -- only the diff (`git diff
  base...HEAD`) and the author's one-line self-reported summary, which the
  reviewer prompt explicitly labels untrusted and to be verified
  independently, per `docs/review-framework.md`.

## Auto-merge (Opcao C, Etapa 12)

The workflow auto-merges (squash + delete branch) when, and only when, both
hold for the exact head commit the reviewer job pushed:

- the independent reviewer's artifact (`state/reviews/agent-pilot-<phase>.yml`)
  is genuinely approved -- validated with the same fingerprint/coverage logic
  (`scripts/review_framework.py`'s `validate_review_document`) the
  human-facing pipeline already requires, not a raw string match on `status`;
- every completion check `instructions/manifest.yml`'s
  `automatic_completion.check_sets` requires for that phase succeeded.

This is a **separate mechanism** from `instructions/03-await-ci-and-merge.md`
and `scripts/ci_completion_state.py`, which remain exactly what they were:
the automatic-completion contract for the older instructions-driven
pipeline (chat/agent operating a `workflow.*_merge_policy` by hand). That
pipeline's CI observation assumes external `pull_request`-triggered check
runs it can poll for. The agent-pilot workflow cannot make that assumption:
it always opens its pull request with the default `GITHUB_TOKEN`, and GitHub
does not cascade events caused by that token to trigger other workflows'
`pull_request` runs. So instead of waiting on separate check runs that would
never start, `scripts/resolve_completion_check_sets.py` resolves which of
the six named checks the phase requires, and the workflow calls each one
inline as a reusable workflow (`workflow_call`) against its own branch --
the same technique already used for
`.github/workflows/agent-pilot-diagnostic-answer-bridge.yml` and documented
in `docs/claude-agent-pilot-etapa9d-diagnostic-answer-form.md`.
`scripts/agent_pilot_merge_decision.py` makes the final call from the
review-document validation plus each check job's actual result (a required
check that only "skipped" -- e.g. an infrastructure hiccup -- blocks exactly
like a failure; only checks the phase does not require are allowed to be
absent). See `docs/claude-agent-pilot-etapa12-auto-merge.md` for the full
design, the false-positive/false-negative findings that motivated it, and
why the digest step never costs an API call.

If either condition is not met, nothing changes from before: the pull
request is left open for a human to decide.

- **No fork trigger.** `workflow_dispatch` requires repository write access
  to invoke, which is the cheapest way to keep `ANTHROPIC_API_KEY` away from
  untrusted input for this first pilot. Issue- or label-triggered runs are
  future work once the manual pilot is validated.

## Token usage and cost estimates

Every `agent_runtime.py` call accumulates the `usage` field the Anthropic API
returns on each round trip (input, output, cache-write, cache-read tokens)
and estimates a USD cost against a hard-coded pricing table
(`MODEL_PRICING_USD_PER_MTOK`, verified against
`platform.claude.com/docs/en/about-claude/pricing` on 2026-08-14). This is a
planning estimate only -- it is never authoritative and the pricing table can
drift if Anthropic changes rates; check the Anthropic Console for real billed
usage.

`scripts/summarize_agent_pilot_usage.py` combines the author's and reviewer's
usage into one number per run and:

- puts it in the pull request body (via `scripts/format_pr_body.py`), so
  whoever reviews the PR sees the estimated cost of the run that produced it;
- appends one JSON line to `state/agent-pilot-usage.jsonl` in the target
  repository, so cost is visible across every phase run over the life of a
  course, not just the latest one.

This is what a course creator publishing an instance can point learners (or
their own budget planning) to for a real estimate, rather than a guess.
Sample record shape (real, from `state/agent-pilot-usage.jsonl` after a
`bootstrap_instance` run with prompt caching active):

```json
{"phase": "bootstrap_instance", "target_repo": "owner/course", "author": {"model": "claude-haiku-4-5-20251001", "input_tokens": 31, "output_tokens": 3866, "cache_creation_input_tokens": 22439, "cache_read_input_tokens": 64375, "total_tokens": 90711, "estimated_cost_usd": 0.05384725}, "reviewer": {"model": "claude-haiku-4-5-20251001", "input_tokens": 51, "output_tokens": 2665, "cache_creation_input_tokens": 22381, "cache_read_input_tokens": 131429, "total_tokens": 156526, "estimated_cost_usd": 0.05449515}, "combined_tokens": 247237, "combined_estimated_cost_usd": 0.1083424, "recorded_at": "2026-08-14T19:12:00+00:00"}
```

Both pilot phases run on Haiku 4.5 (the cheapest tier). Real runs against the
same disposable test repository (see `docs/claude-agent-pilot-etapa3.md` for
the full Etapa 3 writeup and sourcing):

| Phase | Run | Combined tokens | Estimated cost | Notes |
|---|---|---|---|---|
| `bootstrap_instance` | Before prompt caching | 215,290 | **$0.24** | `cache_creation_input_tokens` and `cache_read_input_tokens` both 0 -- every round trip resent the full system prompt and growing history from scratch |
| `bootstrap_instance` | After prompt caching | 247,237 | **$0.108** | `input_tokens` dropped to near-zero (31 / 51); almost everything became `cache_read_input_tokens` at 10% of input price |
| `configure_intake` | After prompt caching (n=1) | 165,957 | **$0.076** | Smaller instruction contract and fewer output artifacts (2 vs. 6) than `bootstrap_instance`, so cheaper even with caching factored in the same way |

Caching roughly **halved the cost** on `bootstrap_instance` despite the token
*count* going up (more total tokens counted, but the overwhelming majority
now bill at the 10% cache-read rate instead of full input price). Treat
$0.07-$0.25 per `bootstrap_instance`/`configure_intake` run as the realistic
range on Haiku 4.5 today, not a guess of "well under a cent" -- an
instruction contract this size, re-read every round trip of an agentic loop,
is genuinely more tokens than it looks like from the file count alone. The
`configure_intake` number is a single sample so far; treat it as a reference
point, not a statistically settled figure.

### Prompt caching

`run_agent()` marks two `cache_control` breakpoints on every request:

- one on the system prompt, which is byte-identical across every round trip
  of a single author or reviewer call;
- one on the last content block of the growing `messages` list, which moves
  forward each round as new tool results are appended.

Concretely: round 1 pays full price and writes a cache entry for the system
prompt plus the initial user message. Round 2 reads both from cache (10% of
input price) and only pays full price for what round 1 added. This makes
total input cost scale roughly linearly with the number of round trips
instead of roughly quadratically. See `_with_trailing_cache_breakpoint` in
`scripts/agent_runtime.py`; `scripts/test_agent_runtime.py` has a test that
asserts the breakpoint moves forward each call without mutating the stored
message history.

Cache writes cost 1.25x base input price and are only worth it if something
downstream actually reads the cache; a call that finishes in one round trip
(no tool use at all) pays the write premium for nothing. In practice every
real pilot run so far has taken multiple rounds (reading several instruction
files before writing anything), so this has consistently paid off.

## Author self-review is no longer part of the pilot path

`instructions/00-bootstrap.md` and `instructions/02-setup-execution.md` were
written for the single-context manual flow (one ChatGPT/Claude conversation
authors the setup *and* reviews its own diff before opening the PR). The
first real pilot run exposed the consequence of handing that same contract to
a split author/reviewer harness verbatim: the author dutifully wrote its own
`state/reviews/setup-v1.yml` with fabricated content, which just sat there as
noise next to the actual independent review.

Both instruction files now carry an explicit exception for the isolated
harness, and `scripts/agent_runtime.py`'s write allowlist enforces it
structurally: `state/reviews/` is no longer a path the author's `write_file`
tool can write to at all (only the reviewer's `submit_review` result,
recorded by the workflow itself, ever lands there in this pilot). The
manual, single-context flow this exception carves out from no longer
exists (Etapa 8 removed it entirely) -- every setup and configure_intake
run today is this isolated harness, so the exception is what actually
applies now, not a special case beside a live default.

## A phase can legitimately have nothing to write

Real dispatch finding (Etapa 9 item 2): running `configure_intake` against an
instance where `bootstrap_instance` had already defaulted every status field
correctly (`intake_provider: github_issue`, which needs no further setup)
left the author with nothing to write. The workflow's own "the author wrote
nothing, fail the job" guard predates this case, and until this fix it could
not tell a legitimate no-op apart from an author that silently skipped its
job -- both looked identical from the outside: empty working tree, job fails.

`scripts/agent_runtime.py`'s `finish_phase` now accepts an explicit
`no_changes_needed` flag plus a required `reason`, but only for phases listed
in `PHASES_ALLOWING_NO_CHANGES_NEEDED` (`configure_intake` today). Calling it
for any other phase is an `AllowlistViolation`, on purpose: `intake`'s
ambiguous/no-candidate case still relies on an empty diff failing the job
loudly, and this flag must never become a way around that.

Critically, `no_changes_needed=true` skips writing a no-op file, not review.
The workflow still pushes the (unchanged) branch and runs the reviewer job
exactly as normal; the reviewer independently re-checks every requirement
against the live repository (it already has `read_file`/`list_dir` for this)
and can reject the claim just like it would reject a wrong diff. The review
artifact `state/reviews/agent-pilot-<phase>.yml` the reviewer writes is
itself new content, so the pull request still exists and still carries a
real, independently-produced verdict -- there is no run of this harness that
merges without one.

## Required repository secret

`ANTHROPIC_API_KEY` -- add it under **Settings -> Secrets and variables ->
Actions** on the repository that will run this workflow. Set a spend limit
for it in the Anthropic Console (proposal, section 6) before running this
against anything but a disposable test repository. Never put the key in a
committed file, an issue, or a workflow log.

## Running it

1. Confirm the secret above is set.
2. Actions tab -> "Agent pilot - setup phase" -> Run workflow.
3. Choose `phase` (`bootstrap_instance` or `configure_intake`) and give
   `target_repo` as `OWNER/REPOSITORY` for the instance you're bootstrapping
   or configuring. `extra_context` is optional free text passed straight to
   the author agent (e.g. a course name if you already know it).
4. The workflow opens a pull request with the author's diff and the
   independent review. Read `state/reviews/agent-pilot-<phase>.yml` for the
   reviewer's checks and any blocking findings before merging.

## Testing

`scripts/test_agent_runtime.py` covers the harness offline -- allowlist
enforcement, the tool-use loop, the budget cap, and the reviewer's
`approved` + non-empty `blocking_findings` rejection -- using a scripted fake
transport so no `ANTHROPIC_API_KEY` or network access is needed to run:

```
python scripts/test_agent_runtime.py
```

There is currently no automated end-to-end test that calls the real API;
that would cost real tokens on every CI run. Validate real-API behavior by
running the workflow against a disposable test repository first.
