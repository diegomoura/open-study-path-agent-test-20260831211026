#!/usr/bin/env python3
"""Minimal Claude coding-agent harness for Open Study Path pilot workflows.

Stage 2 of the multi-agent work proposal: this is the first module that makes
a *real* Anthropic API call. Everything in stage 1 (scripts/agent_model_resolution.py,
scripts/validate_model_config.py) stayed pure logic -- this module is the runtime
that actually sends a request and executes what comes back, scoped to one phase
of instructions/manifest.yml.

Design choices that matter for safety, not just style:

- The model never gets raw filesystem or shell access. It gets three tools
  (read_file, list_dir, write_file for authors; read_file, list_dir,
  submit_review for reviewers) implemented in Python, and every write is
  checked against a deterministic allowlist derived from
  instructions/02-setup-execution.md ("Allowed setup diff") *before* it
  touches disk. An agent asking to write outside the allowlist gets a tool
  error, not a bypass -- the CI-style guardrail described in the work
  proposal applies to agent-written diffs too, not only to human ones.
- Author and reviewer are always two separate `run_agent()` calls with their
  own fresh message history. The reviewer is never handed the author's
  transcript -- only the phase's review contract, the resulting diff, and
  read access to the repository. See docs/claude-agent-pilot.md.
- The HTTP transport is injectable (`transport` parameter) purely so this
  module can be unit-tested offline, without an API key or network access.
  Production code paths always go through `anthropic_transport`.

Stage: Etapa 4 (proposal, section 7, step 4) adds a second, narrower tool
group -- GitHub Issues read/label access -- gated to the `intake` phase only.
The repository these tools operate against is always resolved from the
`GITHUB_REPOSITORY` environment variable that GitHub Actions sets
automatically for the workflow's own repository, never from a
workflow_dispatch input: `instructions/10-intake.md` requires searching only
"the instance repository", and taking that identity from user-controlled
input would let a crafted dispatch point the tool at an unrelated repo. Issue
*classification* itself is never left to the model's judgment: the
`resolve_intake_candidates` tool calls the existing deterministic
`scripts/intake_resolution.py` algorithm directly, exactly as
`instructions/10-intake.md` requires ("Apply the algorithm in
scripts/intake_resolution.py; do not replace it with similarity or
newest-issue heuristics").
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from agent_model_resolution import AGENT_CATALOG, resolve_effective_models
from ensure_repository_labels import github_request_factory
from github_issues_backend import GitHubIssuesBackend
from intake_resolution import DISCOVERY_LABEL, IMPORTED_LABEL, IntakeIssue, resolve_candidates
from assessment_resolution import (
    ASSESSMENT_LABEL,
    GRADED_LABEL,
    SUBMITTED_LABEL,
    AssessmentIssue,
    resolve_candidates as resolve_assessment_candidates_deterministic,
)
from task_projection_engine import (
    ProjectionError,
    TopicProjection,
    apply_assessment_result,
    publish_projection,
)

GITHUB_API_URL_DEFAULT = "https://api.github.com"
RequestJson = Callable[[str, str, dict[str, Any] | None], Any]

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096

# Per-phase override for max_tokens (the per-response output cap sent to the
# API), same reasoning as PHASE_MAX_TOOL_ITERATIONS below. Found necessary
# during the same Etapa 5b dispatch: the reviewer, writing a full curriculum
# review artifact against a real materialized lesson (17-element content
# check, source verification, outcome traceability), hit stop_reason
# "max_tokens" at the 4096 default -- the response was truncated mid-turn,
# never producing a complete tool_use block, so the run ended without
# finishing even though the model was doing real, correct work. Raising this
# to 8192 was not enough either -- a subsequent dispatch showed the AUTHOR
# also hitting max_tokens at 8192, because a single write_file call
# containing a full lesson module (or a review artifact) can by itself
# consume most of one turn's budget. Verified before raising further:
# Claude Sonnet 5 supports up to 128,000 output tokens on the standard
# synchronous Messages API (no beta header required, unlike the old Sonnet
# 3.5 8192-token beta), and max_tokens does not affect billing or rate
# limits -- it is a cap on the response, not a reservation, so there is no
# cost or rate downside to setting it generously above what any single turn
# should realistically need. A per-phase override, not a raised global
# default, for the same reason as the tool-iteration budget: simpler phases
# don't need more room, and a larger cap everywhere would raise the ceiling
# on how much a runaway response could cost before this safety rail catches
# it.
PHASE_MAX_TOKENS: dict[str, int] = {
    # Etapa 9 item 2 real dispatch finding: the preemptive 16384 (set at
    # this table's introduction, reasoning by analogy to replan/
    # generate_proposal below) was not enough -- a real generate_detailed
    # dispatch hit stop_reason "max_tokens" and never reached finish_phase.
    # Raised straight to 32768, matching evaluate's already-confirmed value
    # below for the same class of large single-turn write (a full lesson
    # module plus its assessment), rather than picking another preemptive
    # number that might just need raising again on the next real dispatch.
    "generate_detailed": 32768,
    # Same class of real dispatch finding as generate_detailed (Etapa 5b):
    # the diagnostic reviewer, writing a full review artifact against real
    # placement evidence (5 required checks), hit stop_reason "max_tokens"
    # at the untouched 4096 default -- this phase was never added to this
    # table when it was first introduced. Same 16384 value, same "no cost
    # or rate downside" reasoning already verified for generate_detailed.
    "diagnostic": 16384,
    # Etapa 6b: not yet confirmed to hit max_tokens itself (the real dispatch
    # that motivated this exhausted tool round trips first, see
    # PHASE_MAX_TOOL_ITERATIONS below), but a full study/roadmap.md rewrite
    # is the same class of large single-file write_file call as
    # generate_detailed's lesson modules -- raised preemptively rather than
    # waiting for a second real dispatch to hit it separately.
    "replan": 16384,
    # Etapa 9 item 2: same reasoning as replan above, preemptively -- this
    # is the phase that writes study/roadmap.md from scratch in the first
    # place (replan only revises it), so if anything this write is at least
    # as large as replan's. The real dispatch that motivated adding
    # generate_proposal to PHASE_MAX_TOOL_ITERATIONS below did not confirm a
    # max_tokens failure specifically (it exhausted tool round trips first),
    # but there is no reason to expect this phase's single largest write to
    # be smaller than replan's already-confirmed-large one.
    "generate_proposal": 16384,
    # Etapa 6d real finding: 16384 (set preemptively in Etapa 6c) was not
    # enough -- a real materialization dispatch hit stop_reason="max_tokens"
    # mid-turn, never reaching finish_phase, almost certainly while writing
    # a single ~300-line materialized module (study/modules/TOPIC-002.md in
    # the run that hit this) in one write_file call alongside grading
    # output in the same turn. generate_detailed itself only ever writes
    # one module per turn without also grading a submission first, so
    # evaluate's mastery path is a strictly heavier single-turn combination
    # than any phase 16384 was already confirmed to cover.
    "evaluate": 32768,
}


def max_tokens_for(phase: str) -> int:
    return PHASE_MAX_TOKENS.get(phase, DEFAULT_MAX_TOKENS)

# USD per million tokens, verified against platform.claude.com/docs/en/about-claude/pricing
# (checked 2026-08-14). Update this table if Anthropic changes rates -- it is
# only used to produce an estimate for the pilot's cost reporting, never sent
# to the API or used for anything billing-authoritative.
#
# cache_write_5m / cache_read multipliers are relative to base input price
# (1.25x and 0.1x respectively, per the pricing page); stored here as
# absolute per-MTok USD for direct lookup instead of as a multiplier, since
# the actual multiplier the API applied per-call isn't reported back to us --
# only raw cache_creation_input_tokens / cache_read_input_tokens counts are.
# 5-minute cache writes are assumed since neither prompt in this harness sets
# a longer TTL.
MODEL_PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0, "cache_write_5m": 1.25, "cache_read": 0.10},
    "claude-sonnet-5": {"input": 2.0, "output": 10.0, "cache_write_5m": 2.50, "cache_read": 0.20},
    "claude-opus-4-8": {"input": 5.0, "output": 25.0, "cache_write_5m": 6.25, "cache_read": 0.50},
}

# Hard cap on tool-use round trips per agent call. This is a runtime safety
# rail independent of any billing cap configured in the Anthropic Console
# (work proposal, section 6): a bug that makes the model loop on tool calls
# stops here instead of draining the budget.
MAX_TOOL_ITERATIONS = 20

# Per-phase override for MAX_TOOL_ITERATIONS. Found necessary during Etapa 5b
# validation: `generate_detailed` materializes a topic contract, lesson
# module, rubric, GitHub Issue Form and a content review in one run
# (instructions/30-generate-path.md) -- reading its ~4 input files
# (roadmap, study.config.yml, intake/diagnostic summaries) plus writing
# those ~5-6 outputs already approaches the default 20-iteration budget
# before accounting for any self-correction, and a real dispatch hit exactly
# this ("author agent did not call its finish tool" -- 20 was tuned for
# simpler phases like intake/publish, not this one). Deliberately a
# per-phase override, not a raised global default: a runaway loop in a
# smaller phase should still be caught quickly, at the original budget.
PHASE_MAX_TOOL_ITERATIONS: dict[str, int] = {
    "generate_detailed": 40,
    # Etapa 9 item 2: a real dispatch (generate_proposal was never
    # real-dispatch-validated before this -- proposal section 7 step 5)
    # hit "did not finish within 20 tool round trips" and failed outright,
    # for the same shape of reason generate_detailed needed 40:
    # instructions/28-propose-path.md has the author read intake and
    # diagnostic summaries, then design and write out a full roadmap
    # covering every module/topic of the curriculum, easily exceeding 20
    # round trips for anything beyond a trivially small subject. This is
    # also the phase the proposal itself (section 3) puts at the highest
    # reasoning tier (curriculum_architect, Opus) precisely because a
    # structural error here propagates through everything generated after
    # it -- cutting the budget short here would silently truncate that
    # same curriculum design work, not just fail cleanly.
    "generate_proposal": 40,
    # Etapa 6b: a real replan dispatch hit "did not finish within 20 tool
    # round trips" and failed outright -- replan needs to read the current
    # roadmap, instance marker, study.config.yml and the evidence that
    # triggered the change, then write a revised roadmap plus a review
    # artifact-worthy diff, easily exceeding the untouched 20 default for
    # the same reason generate_detailed needed 40. Same value, same
    # reasoning, confirmed necessary by an actual failed run rather than
    # applied preemptively.
    "replan": 40,
    # Etapa 6c: same preemptive reasoning as PHASE_MAX_TOKENS above --
    # resolving the issue, reading the module/rubric/prior attempts, then
    # writing per-question feedback plus the attempt record is at least as
    # many round trips as replan's roadmap rewrite.
    "evaluate": 40,
}


def max_tool_iterations_for(phase: str) -> int:
    return PHASE_MAX_TOOL_ITERATIONS.get(phase, MAX_TOOL_ITERATIONS)


# The exact "Allowed setup diff" list from instructions/02-setup-execution.md,
# duplicated here deliberately rather than parsed out of the markdown: this
# list is a safety boundary and must fail closed (require a code change and
# review) if the instruction file's prose ever changes shape.
SETUP_ALLOWED_EXACT_PATHS: tuple[str, ...] = (
    ".open-study-path/instance.yml",
    "study.config.yml",
    "state/intake-summary.json",
    "state/progress.json",
    "state/integrations.json",
    "study/roadmap.md",
    "README.md",
)
SETUP_ALLOWED_PREFIXES: tuple[str, ...] = ()
# NOTE: instructions/02-setup-execution.md's "Allowed setup diff" also lists
# `state/reviews/<setup-operation>.yml` -- but that's written by whichever
# context runs the review. In the isolated harness that's always the
# reviewer agent, which never gets write_file (it writes its verdict through
# submit_review, recorded by the workflow step, not by touching disk itself).
# The author is deliberately given no prefix-based write access here: letting
# it write anywhere under state/reviews/ would let it author its own
# "independent" review, which is exactly the failure mode this whole
# author/reviewer split exists to prevent. See docs/claude-agent-pilot.md.

# The exact intake domain-output list from instructions/10-intake.md ("Pull
# request and merge": "a PR limited to the instance marker, study.config.yml,
# state/intake-summary.json and one intake review artifact"). The review
# artifact itself is excluded here for the same reason state/reviews/ is
# excluded from SETUP_ALLOWED_*: only the reviewer's submit_review result,
# recorded by the workflow, writes there.
INTAKE_ALLOWED_EXACT_PATHS: tuple[str, ...] = (
    ".open-study-path/instance.yml",
    "study.config.yml",
    "state/intake-summary.json",
)
INTAKE_ALLOWED_PREFIXES: tuple[str, ...] = ()

# The exact publish domain-output list from instructions/41-task-backend-
# projection.md's "Durable operation contract": state/integrations.json is
# the complete authoritative integration state; state/operations/<id>.json
# is the resumable technical journal; study/integrations.md is the rendered
# learner-facing summary ("render study/integrations.md from authoritative
# state" -- read-back step 11). All three are domain output for this phase,
# unlike the review artifact under state/reviews/.
PUBLISH_ALLOWED_EXACT_PATHS: tuple[str, ...] = (
    "state/integrations.json",
    "study/integrations.md",
)
PUBLISH_ALLOWED_PREFIXES: tuple[str, ...] = ("state/operations/",)

# The exact proposal domain-output list from instructions/28-propose-path.md's
# "Outputs" section: only the roadmap and the instance marker's proposal
# state. Everything else generate touches later (study/topics/, study/
# modules/, ...) belongs to the detailed_generation suboperation, not this
# one -- instructions/28-propose-path.md is explicit: "Do not create
# study/topics/, modules, rubrics, assessment forms, flashcards or
# integration projections during this suboperation."
PROPOSAL_ALLOWED_EXACT_PATHS: tuple[str, ...] = (
    "study/roadmap.md",
    ".open-study-path/instance.yml",
)
PROPOSAL_ALLOWED_PREFIXES: tuple[str, ...] = ()

# The exact detailed-generation domain-output list from instructions/30-
# generate-path.md's "Content-generation strategy" and "Planning contract"
# sections. Study slides were removed entirely from this pilot (see
# docs/claude-agent-pilot-etapa10-remove-slides.md); there is no slides
# path here and no toggle to turn one on.
GENERATE_DETAILED_ALLOWED_EXACT_PATHS: tuple[str, ...] = (
    "study/roadmap.md",
    ".open-study-path/instance.yml",
    "study/integrations.md",
)
GENERATE_DETAILED_ALLOWED_PREFIXES: tuple[str, ...] = (
    "study/topics/",
    "study/modules/",
    "study/assessments/",
    "state/content-reviews/",
    ".github/ISSUE_TEMPLATE/assessment-",
)

# The exact diagnostic domain-output list from instructions/20-diagnostic.md's
# "Diagnostic pull-request policy": only the instance marker and the
# diagnostic summary. Independently cross-checked against
# scripts/review_framework.py's own `_allowed_domain_path` for the
# "diagnostic" profile, which lists exactly these same two paths.
DIAGNOSTIC_ALLOWED_EXACT_PATHS: tuple[str, ...] = (
    ".open-study-path/instance.yml",
    "state/diagnostic-summary.json",
)
DIAGNOSTIC_ALLOWED_PREFIXES: tuple[str, ...] = ()

# Etapa 6a (docs/claude-agent-pilot-etapa6-design.md, section 3.2): copied
# directly from scripts/review_framework.py's phase_allows_artifact("progress"),
# which already restricted this exact pair before any agent harness touched
# `track` -- this is the one phase in this pilot where the deterministic
# review-framework side predates and defines the allowlist, rather than the
# allowlist being derived from an instruction file's own "Outputs" prose.
# instructions/50-track-progress.md only ever persists state/progress.json
# and state/integrations.json; it never writes study/ or .open-study-path/.
TRACK_ALLOWED_EXACT_PATHS: tuple[str, ...] = (
    "state/progress.json",
    "state/integrations.json",
)
TRACK_ALLOWED_PREFIXES: tuple[str, ...] = ()

# Etapa 6b (docs/claude-agent-pilot-etapa6-design.md, section 4): copied
# directly from review_framework.py's phase_allows_artifact("replan"), same
# pattern as TRACK_ALLOWED_* above. Note the prefix-only approximation:
# phase_allows_artifact additionally requires assessment-topic-*.yml paths to
# *end* in .yml, but is_write_allowed() only supports prefix matching, not a
# combined prefix+suffix rule -- a non-.yml file under this prefix would
# pass this coarser gate and still get caught by the precise rule in
# validate_review_framework.py's real CI check. Widening is_write_allowed()
# to support suffix constraints for this one phase was judged not worth
# touching shared matching logic every other phase also relies on.
REPLAN_ALLOWED_EXACT_PATHS: tuple[str, ...] = (
    ".open-study-path/instance.yml",
    "study.config.yml",
    "state/progress.json",
)
REPLAN_ALLOWED_PREFIXES: tuple[str, ...] = (
    "study/",
    ".github/ISSUE_TEMPLATE/assessment-topic-",
)

# Etapa 6c (docs/claude-agent-pilot-etapa6-design.md, section 5.3) started
# with a deliberately *narrower* slice of review_framework.py's
# phase_allows_artifact("assessment") than the full profile allows, to force
# a fail-closed refusal at a code boundary while auto-materialization wasn't
# wired yet (migration in replan). Etapa 6d wires that chained path
# (instructions/57-materialize-next-content.md,
# 38-finalize-generated-bundle.md), so the allowlist now matches
# phase_allows_artifact("assessment") exactly: study/topics/, study/modules/,
# study/flashcards/, study/assessments/ (a newly materialized topic's own
# rubric, not just the just-graded one already covered by
# state/assessments/), study/roadmap.md, study/integrations.md and
# assessment-topic-*.yml join the grading-only exact paths from 6c.
EVALUATE_ALLOWED_EXACT_PATHS: tuple[str, ...] = (
    "state/progress.json",
    "state/integrations.json",
    "study/roadmap.md",
    "study/integrations.md",
)
EVALUATE_ALLOWED_PREFIXES: tuple[str, ...] = (
    "state/assessments/",
    "study/topics/",
    "study/modules/",
    "study/flashcards/",
    "study/assessments/",
    ".github/ISSUE_TEMPLATE/assessment-topic-",
    # Etapa 6d real finding: a real materialization dispatch needed both of
    # these and had neither. generate_detailed's own allowlist already has
    # state/content-reviews/ (the independent content-review artifact
    # 36-review-course-content.md requires for a newly materialized topic --
    # evaluate's materialization path produces the exact same review
    # obligation); state/operations/ is publish's own operation-journal
    # prefix, needed here because evaluate now calls the same
    # run_publish_projection engine and must be able to persist a journal
    # entry on a failed/partial attempt for auditability, per
    # instructions/manifest.yml listing state/operations/ as an explicit
    # evaluate-phase output. Without this, a real dispatch's author
    # correctly refused to write the journal rather than violate the
    # allowlist -- but that meant a failed projection left no audit trail.
    "state/content-reviews/",
    "state/operations/",
)

# Which allowlist applies to which manifest phase. `generate_proposal` is a
# harness-level key for the `proposal` suboperation of manifest.yml's
# `generate` phase (instructions/28-propose-path.md) -- Etapa 5's first
# slice (proposal, section 7, step 5). `generate_detailed` is the second
# slice, the `detailed_generation` suboperation
# (instructions/30-generate-path.md).
# `diagnostic` is Etapa 4b -- see the module docstring addendum below and
# docs/claude-agent-pilot-etapa4b-diagnostic-design.md for why it runs on a
# completely different trigger (issue_comment, not workflow_dispatch).
PHASE_ALLOWLISTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "bootstrap_instance": (SETUP_ALLOWED_EXACT_PATHS, SETUP_ALLOWED_PREFIXES),
    "configure_intake": (SETUP_ALLOWED_EXACT_PATHS, SETUP_ALLOWED_PREFIXES),
    "intake": (INTAKE_ALLOWED_EXACT_PATHS, INTAKE_ALLOWED_PREFIXES),
    "publish": (PUBLISH_ALLOWED_EXACT_PATHS, PUBLISH_ALLOWED_PREFIXES),
    "generate_proposal": (PROPOSAL_ALLOWED_EXACT_PATHS, PROPOSAL_ALLOWED_PREFIXES),
    "generate_detailed": (GENERATE_DETAILED_ALLOWED_EXACT_PATHS, GENERATE_DETAILED_ALLOWED_PREFIXES),
    "diagnostic": (DIAGNOSTIC_ALLOWED_EXACT_PATHS, DIAGNOSTIC_ALLOWED_PREFIXES),
    "track": (TRACK_ALLOWED_EXACT_PATHS, TRACK_ALLOWED_PREFIXES),
    "replan": (REPLAN_ALLOWED_EXACT_PATHS, REPLAN_ALLOWED_PREFIXES),
    "evaluate": (EVALUATE_ALLOWED_EXACT_PATHS, EVALUATE_ALLOWED_PREFIXES),
}

# Agent ids that exist as real rows in AGENT_CATALOG for the pilot phases.
# AGENT_CATALOG's own `phase` field for curriculum_architect/curriculum_
# reviewer is the manifest id "generate" (matching manifest.yml, which
# doesn't split proposal vs detailed_generation into separate ids) -- that
# field is descriptive only. resolve_effective_models() looks agents up by
# id, never by this harness's phase key, so introducing a harness-only
# `generate_proposal` key here causes no lookup mismatch.
PHASE_AUTHOR_AGENT: dict[str, str] = {
    "bootstrap_instance": "bootstrap",
    "configure_intake": "configure_intake",
    "intake": "intake_resolution",
    "publish": "publish",
    "generate_proposal": "curriculum_architect",
    "generate_detailed": "content_author",
    "diagnostic": "diagnostic",
    "track": "track",
    "replan": "replan",
    "evaluate": "evaluate",
}

# Etapa 4b (docs/claude-agent-pilot-etapa4b-diagnostic-design.md): unlike
# every other phase, `diagnostic` never runs via workflow_dispatch. It is
# triggered once per learner reply (issue_comment on the session issue,
# .github/workflows/agent-pilot-diagnostic.yml), and each invocation
# reconstructs the whole running Q&A state from the issue's comment thread
# (scripts/build_diagnostic_context.py) rather than from any harness-side
# memory -- the same "context from artifacts, never memory" discipline as
# every other phase, just triggered by a different event. Most turns only
# post the next question (a comment) and touch no repository file at all;
# only the terminal turn, once evidence is sufficient, writes
# state/diagnostic-summary.json/instance.yml and opens a PR. Phases in this
# set get post_issue_comment/list_issue_comments in addition to whatever
# else their allowlist covers.
PHASES_WITH_ISSUE_COMMENTS: frozenset[str] = frozenset({"diagnostic"})

# Phases where the RepoTools instance also gets a small, separate GitHub
# Issues tool group, in addition to the repo-file tools every phase gets.
# `publish` is restricted to the github_issues task-manager backend only --
# Trello/Todoist need their own Secret and their own adapter, deferred (see
# docs/claude-agent-pilot.md's Scope section).
# Etapa 6a: `track` needs read-only access to the authoritative task issue's
# current state (instructions/50-track-progress.md's "Synchronize activity
# state from the single authoritative task backend") to detect activity
# signals -- but never list_intake_issues (that tool is scoped to the intake
# discovery label, unrelated to task-tracking issues) and never
# label_github_issue/post_issue_comment. See _track_issue_read_tool() below.
# Etapa 6c: `evaluate` needs the fullest GitHub Issues access of any phase so
# far -- read (resolve + re-read the assessment issue), write a comment
# (the evaluation itself), and both add and remove specific labels
# (assessment:submitted -> assessment:graded / assessment:recovery-required).
# See PHASE_ALLOWED_APPLIED_LABELS / PHASE_ALLOWED_REMOVED_LABELS below for
# the exact, hardcoded label sets -- same "the model supplies data, never
# the allowlist" shape as INTAKE_AUTHOR_ALLOWED_LABEL already established.
PHASES_WITH_GITHUB_ISSUES: frozenset[str] = frozenset(
    {"intake", "publish", "diagnostic", "track", "evaluate"}
)

# The only label the intake author is ever allowed to apply. Restricting this
# at the tool layer (not just in the prompt) means a model that misreads its
# own instructions cannot label an unrelated issue or invent a new label --
# the same "fail closed on a code boundary, not a prompt boundary" posture
# `write_file`'s allowlist check already applies to file writes.
INTAKE_AUTHOR_ALLOWED_LABEL = IMPORTED_LABEL

# Etapa 6c: the exact labels `evaluate` may apply or remove, straight from
# instructions/55-evaluate-topic.md's "Finalize repository and issue state"
# section -- generalizes the single-label shape INTAKE_AUTHOR_ALLOWED_LABEL
# established into a per-phase set, since evaluate needs two different
# outcomes (mastered vs. recovery-required) rather than one fixed label.
RECOVERY_REQUIRED_LABEL = "assessment:recovery-required"
PHASE_ALLOWED_APPLIED_LABELS: dict[str, frozenset[str]] = {
    "intake": frozenset({INTAKE_AUTHOR_ALLOWED_LABEL}),
    "evaluate": frozenset({GRADED_LABEL, RECOVERY_REQUIRED_LABEL}),
}
PHASE_ALLOWED_REMOVED_LABELS: dict[str, frozenset[str]] = {
    "evaluate": frozenset({SUBMITTED_LABEL}),
}

# Etapa 9 item 2 (real dispatch finding): phases where the repository can
# already fully satisfy the phase's contract before the author even runs --
# configure_intake's github_issue path needs zero setup once bootstrap_instance
# has defaulted every status field correctly, so a legitimate run can have
# nothing left to write. finish_phase's no_changes_needed flag is only
# accepted for phases in this set; every other phase keeps the original
# "wrote nothing == the workflow's no-diff guard fails the job" behavior,
# which intake's ambiguous/no-candidate case still relies on staying strict.
# Etapa 9d: hidden marker post_issue_comment() appends to every diagnostic
# author comment, structurally -- agent-pilot-diagnostic.yml's loop guard
# treats a github-actions[bot] comment as the author's own turn (skip it)
# only when this exact marker is present, which is what lets the
# diagnostic-answer bridge's unmarked, bot-authored repost of a learner's
# real answers through the same guard.
DIAGNOSTIC_AUTHOR_COMMENT_MARKER = "<!-- open-study-path:diagnostic-turn -->"

PHASES_ALLOWING_NO_CHANGES_NEEDED: frozenset[str] = frozenset({"configure_intake"})


class AllowlistViolation(RuntimeError):
    """Raised when a tool call would write (or read outside the repo) improperly."""


class AgentBudgetExceeded(RuntimeError):
    """Raised when MAX_TOOL_ITERATIONS is hit without the agent finishing.

    Carries `tool_call_names`, the ordered sequence of every tool call made
    before the budget ran out, so a caller can tell steady, varied progress
    (raise the budget further) apart from a repeated/looping pattern (a real
    behavioral bug, not a budget problem) -- without this, the only signal
    was "did not call its finish tool", which looks identical either way.
    """

    def __init__(self, message: str, tool_call_names: list[str] | None = None) -> None:
        super().__init__(message)
        self.tool_call_names = tool_call_names or []


def resolve_phase_reviewer_model(phase: str, config: Mapping[str, Any]) -> str:
    """Resolve the model a *generic* phase_review pass should use.

    Only curriculum/content/publish have a dedicated reviewer row in
    AGENT_CATALOG. Every other phase uses the generic
    instructions/04-review-generated-artifacts.md contract, and the work
    proposal (section 3, last row) states the rule explicitly: a generic
    reviewer "herda o tier da fase" -- it uses the same effective tier as
    that phase's author agent, whatever the dial/override resolved to.
    """
    author_agent_id = PHASE_AUTHOR_AGENT.get(phase)
    if author_agent_id is None:
        raise ValueError(f"no author agent registered for phase: {phase}")
    resolved = resolve_effective_models(config)
    return resolved[author_agent_id].model


def normalize_relative_path(root: Path, candidate: str) -> Path:
    """Resolve `candidate` under `root`, rejecting escapes and absolute paths."""
    if not candidate or candidate.startswith(("/", "~")) or ".." in Path(candidate).parts:
        raise AllowlistViolation(f"refusing unsafe path: {candidate!r}")
    resolved = (root / candidate).resolve()
    root_resolved = root.resolve()
    if root_resolved not in resolved.parents and resolved != root_resolved:
        raise AllowlistViolation(f"path escapes repository root: {candidate!r}")
    return resolved


def is_write_allowed(phase: str, relative_path: str) -> bool:
    exact_paths, prefixes = PHASE_ALLOWLISTS.get(phase, ((), ()))
    normalized = relative_path.replace(os.sep, "/")
    if normalized in exact_paths:
        return True
    return any(normalized.startswith(prefix) for prefix in prefixes)


@dataclass
class ToolCallResult:
    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass
class UsageTotals:
    """Accumulated token usage across every API round trip in one run_agent() call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def add(self, usage: Mapping[str, Any]) -> None:
        self.input_tokens += int(usage.get("input_tokens", 0) or 0)
        self.output_tokens += int(usage.get("output_tokens", 0) or 0)
        self.cache_creation_input_tokens += int(usage.get("cache_creation_input_tokens", 0) or 0)
        self.cache_read_input_tokens += int(usage.get("cache_read_input_tokens", 0) or 0)

    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    def estimated_cost_usd(self, model: str) -> float | None:
        """Return an estimated USD cost, or None if `model` isn't in the pricing table.

        This is an estimate for reporting only (see MODEL_PRICING_USD_PER_MTOK) --
        it is never authoritative. Check the Anthropic Console for real billed
        usage; this exists so a course creator deciding whether to run the
        pilot has a number to look at before they do, not so anyone can skip
        checking their actual invoice.
        """
        rates = MODEL_PRICING_USD_PER_MTOK.get(model)
        if rates is None:
            return None
        return (
            self.input_tokens * rates["input"]
            + self.output_tokens * rates["output"]
            + self.cache_creation_input_tokens * rates["cache_write_5m"]
            + self.cache_read_input_tokens * rates["cache_read"]
        ) / 1_000_000

    def as_dict(self, model: str) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "total_tokens": self.total_tokens(),
            "estimated_cost_usd": self.estimated_cost_usd(model),
        }


@dataclass
class AgentRun:
    """Outcome of one run_agent() call -- author or reviewer."""

    phase: str
    role: str
    model: str
    transcript: list[dict[str, Any]] = field(default_factory=list)
    finished: bool = False
    finish_payload: dict[str, Any] | None = None
    files_written: list[str] = field(default_factory=list)
    usage: UsageTotals = field(default_factory=UsageTotals)


class RepoTools:
    """Implements the small set of tools exposed to the model.

    `role` gates which tools are actually offered: authors get write_file and
    finish_phase, reviewers get submit_review instead of write access.

    `github_request`/`github_repository` are only required when `phase` is in
    PHASES_WITH_GITHUB_ISSUES. They stay optional constructor args (rather
    than always-on) so every other phase's tests keep working without a
    GitHub token or network access -- the same reasoning `transport` in
    `run_agent()` already follows for the Anthropic call.
    """

    def __init__(
        self,
        root: Path,
        phase: str,
        role: str,
        github_request: RequestJson | None = None,
        github_repository: str | None = None,
    ) -> None:
        self.root = root
        self.phase = phase
        self.role = role
        self.files_written: list[str] = []
        self.finish_payload: dict[str, Any] | None = None
        self.finished = False
        self.github_request = github_request
        self.github_repository = github_repository
        self._issue_summaries: dict[int, dict[str, Any]] | None = None
        self._assessment_issue_summaries: dict[int, dict[str, Any]] | None = None
        self.labels_applied: list[tuple[int, str]] = []
        self.labels_removed: list[tuple[int, str]] = []
        self._last_candidate_resolution_state: str | None = None
        self._last_publish_status: str | None = None
        self._diagnostic_comment_posted_this_turn: bool = False

    def read_file(self, path: str) -> str:
        target = normalize_relative_path(self.root, path)
        if not target.is_file():
            raise AllowlistViolation(f"no such file: {path!r}")
        return target.read_text(encoding="utf-8")

    def compute_sha256(self, path: str) -> str:
        """Return the real sha256 of a file's exact current bytes.

        Exists so the reviewer never has to guess or invent a fingerprint --
        docs/review-framework.md binds review approval to exact byte
        fingerprints specifically so a stale review can't authorize a changed
        output; a model-generated hex string that merely looks like a sha256
        defeats that guarantee silently.
        """
        target = normalize_relative_path(self.root, path)
        if not target.is_file():
            raise AllowlistViolation(f"no such file: {path!r}")
        return sha256(target.read_bytes()).hexdigest()

    def list_dir(self, path: str) -> str:
        target = normalize_relative_path(self.root, path or ".")
        if not target.is_dir():
            raise AllowlistViolation(f"no such directory: {path!r}")
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
        return "\n".join(entries) if entries else "(empty)"

    def _require_github(self) -> tuple[RequestJson, str]:
        if self.phase not in PHASES_WITH_GITHUB_ISSUES:
            raise AllowlistViolation(f"GitHub Issues tools are not available for phase {self.phase!r}")
        if self.github_request is None or not self.github_repository:
            raise AllowlistViolation(
                "GitHub Issues tools are enabled for this phase but no github_request/"
                "github_repository was configured -- this is a harness wiring bug, not a "
                "model error"
            )
        return self.github_request, self.github_repository

    def list_intake_issues(self) -> str:
        """List open, non-PR issues carrying the discovery label, instance repo only.

        Fetches summaries only (number, title, labels, author, created_at) --
        never the body -- to keep this read cheap. `read_github_issue` fetches
        one full issue when the model actually needs its rendered body.
        Results are cached on this instance so `resolve_intake_candidates` can
        reuse them without a second API round trip in the same run.
        """
        request_json, repository = self._require_github()
        raw = request_json(
            "GET",
            f"/repos/{repository}/issues?labels={DISCOVERY_LABEL}&state=all&per_page=100",
            None,
        )
        summaries: dict[int, dict[str, Any]] = {}
        for item in raw or []:
            summaries[item["number"]] = {
                "number": item["number"],
                "title": item.get("title", ""),
                "labels": [label.get("name", "") for label in item.get("labels", [])],
                "author_login": (item.get("user") or {}).get("login"),
                "is_pull_request": "pull_request" in item,
                "created_at": item.get("created_at"),
            }
        self._issue_summaries = summaries
        return json.dumps(list(summaries.values()), indent=2)

    def read_github_issue(self, number: int) -> str:
        """Fetch one issue's full rendered body plus its identity fields."""
        request_json, repository = self._require_github()
        item = request_json("GET", f"/repos/{repository}/issues/{number}", None)
        return json.dumps(
            {
                "number": item["number"],
                "title": item.get("title", ""),
                "body": item.get("body") or "",
                "labels": [label.get("name", "") for label in item.get("labels", [])],
                "author_login": (item.get("user") or {}).get("login"),
                "is_pull_request": "pull_request" in item,
                "created_at": item.get("created_at"),
            },
            indent=2,
        )

    def resolve_intake_candidates(
        self,
        expected_headings: list[str],
        required_response_headings: list[str],
        consent_heading: str,
    ) -> str:
        """Run the real scripts/intake_resolution.py classification, not a model guess.

        instructions/10-intake.md requires applying this exact algorithm and
        forbids replacing it with similarity or newest-issue heuristics; doing
        the classification here in Python, from data the model cannot edit,
        makes that requirement structural instead of advisory. The model
        still supplies expected_headings/required_response_headings/
        consent_heading because those come from reading the checked-in form
        contract (.github/ISSUE_TEMPLATE/create-study-path.yml via read_file),
        which is exactly the "current repository form contract, not a hidden
        comment" the instruction requires -- the harness does not duplicate
        that YAML parsing.

        allowed_authors and imported_references are resolved by the harness
        itself: allowed_authors from the known instance owner in
        .open-study-path/instance.yml when present, imported_references from
        state/intake-summary.json.source_reference when present. The model
        never supplies either -- both are used to reject candidates, and a
        model-supplied allowlist could be used to admit one instead.
        """
        request_json, repository = self._require_github()
        if self._issue_summaries is None:
            self.list_intake_issues()
        assert self._issue_summaries is not None

        allowed_authors = self._known_instance_owner()
        imported_references = self._known_imported_references()

        candidates: list[IntakeIssue] = []
        for summary in self._issue_summaries.values():
            if summary["is_pull_request"] or IMPORTED_LABEL in summary["labels"]:
                # No need to fetch the body for something already excluded by
                # a cheap identity check -- saves an API call per stale issue.
                candidates.append(
                    IntakeIssue(
                        number=summary["number"],
                        title=summary["title"],
                        body="",
                        labels=frozenset(summary["labels"]),
                        is_pull_request=summary["is_pull_request"],
                        source_reference=f"github_issue:{repository}#{summary['number']}",
                        author_login=summary["author_login"],
                    )
                )
                continue
            full = json.loads(self.read_github_issue(summary["number"]))
            candidates.append(
                IntakeIssue(
                    number=full["number"],
                    title=full["title"],
                    body=full["body"],
                    labels=frozenset(full["labels"]),
                    is_pull_request=full["is_pull_request"],
                    source_reference=f"github_issue:{repository}#{full['number']}",
                    author_login=full["author_login"],
                )
            )

        resolution = resolve_candidates(
            candidates,
            expected_headings,
            imported_references,
            required_response_headings=required_response_headings,
            consent_heading=consent_heading or None,
            allowed_authors=allowed_authors,
        )
        self._last_candidate_resolution_state = resolution.state
        return json.dumps(
            {
                "state": resolution.state,
                "accepted": [decision.__dict__ for decision in resolution.accepted],
                "rejected": [decision.__dict__ for decision in resolution.rejected],
            },
            indent=2,
        )

    def list_assessment_issues(self) -> str:
        """List open+closed issues carrying assessment:submitted, instance repo only.

        Same cheap-summary-then-full-body shape as list_intake_issues.
        Filtering server-side by the most specific already-known label
        (assessment:submitted, not the broader assessment) keeps this to
        exactly the candidates classify_issue's rules 1-2 would accept
        anyway on that axis.
        """
        request_json, repository = self._require_github()
        raw = request_json(
            "GET",
            f"/repos/{repository}/issues?labels={SUBMITTED_LABEL}&state=all&per_page=100",
            None,
        )
        summaries: dict[int, dict[str, Any]] = {}
        for item in raw or []:
            summaries[item["number"]] = {
                "number": item["number"],
                "title": item.get("title", ""),
                "labels": [label.get("name", "") for label in item.get("labels", [])],
                "author_login": (item.get("user") or {}).get("login"),
                "is_pull_request": "pull_request" in item,
                "created_at": item.get("created_at"),
            }
        self._assessment_issue_summaries = summaries
        return json.dumps(list(summaries.values()), indent=2)

    def resolve_assessment_candidates(self, topic_id: str, issue_number: int | None = None) -> str:
        """Run the real scripts/assessment_resolution.py classification, not a model guess.

        instructions/55-evaluate-topic.md requires this exact algorithm and
        explicitly forbids choosing an arbitrary newest issue -- same
        rationale as resolve_intake_candidates. Two modes, matching the two
        supported learner commands:

        - issue_number given ("...Avalie a issue #<número>."): read that one
          issue and validate it against topic_id, no search.
        - issue_number omitted ("...Avalie minhas respostas."): search
          list_assessment_issues() and classify every candidate.

        recorded_issue_numbers and last_attempt_created_at come from the
        harness reading state/assessments/<topic_id>/ itself (like
        resolve_intake_candidates reads state/intake-summary.json), never
        from the model -- both are used to reject candidates, and a
        model-supplied value could be used to admit one instead.
        """
        request_json, repository = self._require_github()
        recorded_issue_numbers, last_attempt_created_at = self._known_assessment_state(topic_id)
        allowed_authors = self._known_instance_owner()

        candidates: list[AssessmentIssue] = []
        if issue_number is not None:
            full = json.loads(self.read_github_issue(issue_number))
            candidates.append(
                AssessmentIssue(
                    number=full["number"],
                    title=full["title"],
                    body=full["body"],
                    labels=frozenset(full["labels"]),
                    created_at=full.get("created_at"),
                    is_pull_request=full["is_pull_request"],
                    author_login=full["author_login"],
                )
            )
        else:
            if self._assessment_issue_summaries is None:
                self.list_assessment_issues()
            assert self._assessment_issue_summaries is not None
            for summary in self._assessment_issue_summaries.values():
                full = json.loads(self.read_github_issue(summary["number"]))
                candidates.append(
                    AssessmentIssue(
                        number=full["number"],
                        title=full["title"],
                        body=full["body"],
                        labels=frozenset(full["labels"]),
                        created_at=full.get("created_at"),
                        is_pull_request=full["is_pull_request"],
                        author_login=full["author_login"],
                    )
                )

        resolution = resolve_assessment_candidates_deterministic(
            candidates,
            topic_id,
            recorded_issue_numbers=recorded_issue_numbers,
            last_attempt_created_at=last_attempt_created_at,
            allowed_authors=allowed_authors,
        )
        return json.dumps(
            {
                "state": resolution.state,
                "accepted": [decision.__dict__ for decision in resolution.accepted],
                "rejected": [decision.__dict__ for decision in resolution.rejected],
            },
            indent=2,
        )

    def _known_assessment_state(self, topic_id: str) -> tuple[list[int], str | None]:
        """Read every recorded attempt for one topic from the repository, not the model.

        Etapa 6c: state/assessments/<topic_id>/attempt-*.json has no
        checked-in JSON schema yet (instructions/55-evaluate-topic.md only
        describes its required fields in prose) -- this reads defensively,
        skipping any file that is not valid JSON or does not carry the two
        fields resolution needs (issue_number, timestamp), rather than
        failing the whole operation on one malformed historical attempt.
        """
        directory = normalize_relative_path(self.root, f"state/assessments/{topic_id}")
        if not directory.is_dir():
            return [], None
        recorded: list[int] = []
        latest: str | None = None
        for path in sorted(directory.glob("attempt-*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            issue_number = data.get("issue_number")
            if isinstance(issue_number, int):
                recorded.append(issue_number)
            timestamp = data.get("timestamp")
            if isinstance(timestamp, str) and timestamp and (latest is None or timestamp > latest):
                latest = timestamp
        return recorded, latest

    def _known_instance_owner(self) -> list[str]:
        marker = normalize_relative_path(self.root, ".open-study-path/instance.yml")
        if not marker.is_file():
            return []
        import yaml  # local import: keep base module dependency-free for offline tests

        data = yaml.safe_load(marker.read_text(encoding="utf-8")) or {}
        owner = (data.get("owner") or {}).get("github_login") if isinstance(data.get("owner"), dict) else None
        return [owner] if owner else []

    def _known_imported_references(self) -> list[str]:
        summary_path = normalize_relative_path(self.root, "state/intake-summary.json")
        if not summary_path.is_file():
            return []
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        reference = data.get("source_reference")
        return [reference] if reference else []

    def label_github_issue(self, number: int, label: str) -> str:
        if self.role != "author":
            raise AllowlistViolation("label_github_issue is not available to this role")
        allowed = PHASE_ALLOWED_APPLIED_LABELS.get(self.phase, frozenset())
        if label not in allowed:
            raise AllowlistViolation(
                f"refusing to apply label {label!r} for phase {self.phase!r}: only "
                f"{sorted(allowed)!r} may be applied"
            )
        request_json, repository = self._require_github()
        request_json("POST", f"/repos/{repository}/issues/{number}/labels", {"labels": [label]})
        self.labels_applied.append((number, label))
        return f"applied label {label!r} to issue #{number}"

    def unlabel_github_issue(self, number: int, label: str) -> str:
        """Remove one label -- currently only evaluate clearing assessment:submitted.

        Mirrors label_github_issue's phase-scoped, hardcoded allowlist shape:
        the model supplies which issue, never which labels are permitted.
        """
        if self.role != "author":
            raise AllowlistViolation("unlabel_github_issue is not available to this role")
        allowed = PHASE_ALLOWED_REMOVED_LABELS.get(self.phase, frozenset())
        if label not in allowed:
            raise AllowlistViolation(
                f"refusing to remove label {label!r} for phase {self.phase!r}: only "
                f"{sorted(allowed)!r} may be removed"
            )
        request_json, repository = self._require_github()
        encoded_label = urllib.parse.quote(label, safe="")
        request_json("DELETE", f"/repos/{repository}/issues/{number}/labels/{encoded_label}", None)
        self.labels_removed.append((number, label))
        return f"removed label {label!r} from issue #{number}"

    def list_issue_comments(self, number: int) -> str:
        """Read the full comment thread of one issue -- the diagnostic session's only state.

        Etapa 4b: each invocation of the diagnostic author reconstructs the
        entire running Q&A exchange from this thread, never from harness-side
        memory (there is none -- every turn is a fresh, isolated process).
        Returns each comment's author, timestamp and body in chronological
        order, exactly as GitHub returns them (no pagination limit applied
        here -- a diagnostic session is capped at 10 questions by
        instructions/20-diagnostic.md's hard maximum, so the thread is always
        small).
        """
        request_json, repository = self._require_github()
        raw = request_json("GET", f"/repos/{repository}/issues/{number}/comments?per_page=100", None)
        comments = [
            {
                "author_login": (item.get("user") or {}).get("login"),
                "created_at": item.get("created_at"),
                "body": item.get("body") or "",
            }
            for item in raw or []
        ]
        return json.dumps(comments, indent=2)

    def post_issue_comment(self, number: int, body: str) -> str:
        """Post one comment -- the diagnostic author's only way to reach the learner.

        Used for both the turn-1 question batch and the terminal completion
        response (instructions/20-diagnostic.md's single-form-batch design,
        Etapa 9c) -- never one question per turn.

        Always appends the hidden loop-prevention marker
        (DIAGNOSTIC_AUTHOR_COMMENT_MARKER) to every comment this posts,
        structurally rather than trusting the model to remember it every
        time: agent-pilot-diagnostic.yml's loop guard skips a re-trigger only
        when a github-actions[bot] comment carries this exact marker, so a
        forgotten marker would make the workflow re-process the author's own
        message as if it were a fresh learner reply. Etapa 9d's diagnostic-
        answer bridge (agent-pilot-diagnostic-answer-bridge.yml) also posts as
        github-actions[bot] but never adds this marker, which is what lets
        its reposted answers through the same guard as a genuine reply.
        """
        if self.role != "author":
            raise AllowlistViolation("post_issue_comment is not available to this role")
        request_json, repository = self._require_github()
        if self.phase == "diagnostic" and DIAGNOSTIC_AUTHOR_COMMENT_MARKER not in body:
            body = f"{body}\n\n{DIAGNOSTIC_AUTHOR_COMMENT_MARKER}"
        request_json("POST", f"/repos/{repository}/issues/{number}/comments", {"body": body})
        self._diagnostic_comment_posted_this_turn = True
        return f"posted comment to issue #{number}"

    def run_publish_projection(
        self,
        topics: list[dict[str, Any]],
        operation_id: str,
        course_name: str,
        routine_mode: str = "none",
    ) -> str:
        """Run the real task_projection_engine.publish_projection() against GitHub Issues.

        This is the single orchestrated tool for the `publish` phase, the
        same pattern `resolve_intake_candidates` already established: the
        deterministic engine in scripts/task_projection_engine.py does all
        matching, idempotency and read-back validation; this method only
        supplies a real backend and translates its result into the JSON the
        model reads back. The model supplies `topics` from the approved
        roadmap (read via read_file) -- it never invents or classifies
        projection state itself.

        On success, returns integration_state/journal/learner_summary for
        the model to persist via write_file. On a known projection failure
        (ambiguous match, partial write, failed read-back validation), returns
        a structured error instead of raising -- these are expected, valid
        outcomes instructions/40-publish-tasks.md explicitly describes
        ("When required publication is blocked, failed, partial or still in
        progress..."), not tool misuse, so they must not crash the run the
        way an AllowlistViolation would.
        """
        if self.role != "author":
            raise AllowlistViolation("run_publish_projection is not available to this role")
        request_json, repository = self._require_github()

        try:
            topic_projections = [TopicProjection(**topic) for topic in topics]
        except (TypeError, ValueError) as exc:
            return json.dumps({"status": "error", "error_type": "InvalidTopicInput", "message": str(exc)})

        previous_integration_state = None
        integrations_path = normalize_relative_path(self.root, "state/integrations.json")
        if integrations_path.is_file():
            previous_integration_state = json.loads(integrations_path.read_text(encoding="utf-8"))

        journal_state = None
        operation_path = normalize_relative_path(self.root, f"state/operations/{operation_id}.json")
        if operation_path.is_file():
            journal_state = json.loads(operation_path.read_text(encoding="utf-8"))

        backend = GitHubIssuesBackend(request_json=request_json, repository=repository)
        try:
            result = publish_projection(
                topics=topic_projections,
                backend=backend,
                operation_id=operation_id,
                journal_state=journal_state,
                previous_integration_state=previous_integration_state,
                course_name=course_name,
                routine_mode=routine_mode,
            )
        except ProjectionError as exc:
            self._last_publish_status = "error"
            journal = getattr(exc, "journal", None)
            return json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "journal": journal,
                }
            )

        self._last_publish_status = "success"
        return json.dumps(
            {
                "status": "success",
                "integration_state": result.integration_state,
                "journal": result.journal,
                "learner_summary": result.learner_summary,
            },
            indent=2,
        )

    def apply_topic_assessment_result(
        self, topics: list[dict[str, Any]], topic_id: str, passed: bool
    ) -> str:
        """Wrap task_projection_engine.apply_assessment_result() for evaluate (Etapa 6d).

        Pure, in-memory transform: sets one topic's canonical_state to
        "completed" (passed=True) or "review_required" (passed=False) in an
        otherwise-unchanged topics list, matching the exact shape
        run_publish_projection expects as input. This is the step between
        "grading concluded mastery/not" and "push that conclusion to
        GitHub" -- the model builds `topics` from the current roadmap (same
        as publish's author already does), calls this to get the updated
        list, then passes the result straight to run_publish_projection.
        Never mutate canonical_state by hand in a write_file call instead
        of through this function -- that would bypass the same
        idempotency/read-back guarantees run_publish_projection depends on.
        """
        if self.role != "author":
            raise AllowlistViolation("apply_topic_assessment_result is not available to this role")
        try:
            topic_projections = [TopicProjection(**topic) for topic in topics]
        except (TypeError, ValueError) as exc:
            return json.dumps({"status": "error", "error_type": "InvalidTopicInput", "message": str(exc)})
        try:
            updated = apply_assessment_result(topic_projections, topic_id=topic_id, passed=passed)
        except KeyError:
            return json.dumps(
                {
                    "status": "error",
                    "error_type": "UnknownTopicId",
                    "message": f"topic_id {topic_id!r} is not present in the supplied topics list",
                }
            )
        return json.dumps({"status": "success", "topics": [asdict(t) for t in updated]}, indent=2)

    def write_file(self, path: str, content: str) -> str:
        if self.role != "author":
            raise AllowlistViolation("write_file is not available to this role")
        if not is_write_allowed(self.phase, path):
            raise AllowlistViolation(
                f"{path!r} is outside the allowed setup diff for phase {self.phase!r} "
                "(instructions/02-setup-execution.md); refusing to write it"
            )
        if (
            self.phase == "intake"
            and path.replace(os.sep, "/") == "state/intake-summary.json"
            and self._last_candidate_resolution_state != "unique"
        ):
            # instructions/10-intake.md never authorizes an intake write
            # without exactly one accepted candidate. A prompt note is not
            # enough on its own -- an earlier real dispatch (Etapa 4,
            # docs/claude-agent-pilot-etapa4.md section 5.2) showed the model
            # using this path as an ad hoc status scratchpad in the
            # `ambiguous` state instead of leaving it untouched. Enforcing it
            # here means that failure mode can no longer happen silently,
            # regardless of what the prompt says.
            raise AllowlistViolation(
                "refusing to write state/intake-summary.json: resolve_intake_candidates "
                f"must return state='unique' first (last observed state: "
                f"{self._last_candidate_resolution_state!r}). For 'none' or 'ambiguous', "
                "report the outcome through finish_phase instead of writing this file."
            )
        if (
            self.phase == "publish"
            and path.replace(os.sep, "/") in {"state/integrations.json", "study/integrations.md"}
            and self._last_publish_status != "success"
        ):
            # Same principle as the intake guard just above, applied before
            # a real dispatch ever surfaces it: instructions/40-publish-
            # tasks.md is explicit that a blocked/failed/partial publication
            # must not be reported as success ("do not set success or
            # sync.last_success_at"). state/integrations.json and study/
            # integrations.md are exactly the authoritative-success and
            # learner-facing-success artifacts -- state/operations/<id>.json
            # is deliberately NOT covered by this guard, since the resumable
            # operation journal must be persisted on every outcome, including
            # a blocked or partial one.
            raise AllowlistViolation(
                f"refusing to write {path!r}: run_publish_projection must return "
                f"status='success' first (last observed status: {self._last_publish_status!r}). "
                "For a blocked/partial/failed publication, persist only "
                "state/operations/<operation-id>.json and report the outcome through "
                "finish_phase."
            )
        target = normalize_relative_path(self.root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.files_written.append(path)
        return f"wrote {len(content)} bytes to {path}"

    def finish_phase(
        self,
        summary: str,
        next_action: str,
        no_changes_needed: bool = False,
        reason: str = "",
    ) -> str:
        if self.role != "author":
            raise AllowlistViolation("finish_phase is not available to this role")
        if self.phase == "diagnostic" and not self._diagnostic_comment_posted_this_turn:
            # Real, achievable structural invariant for a phase with no
            # deterministic sufficiency signal to gate on (unlike intake's
            # resolve_intake_candidates or publish's run_publish_projection
            # status): every diagnostic turn must tell the learner something
            # -- the next question or the completion response -- before
            # ending. This does not verify the *sufficiency* judgment itself
            # (that remains the model's call), only that the turn never ends
            # silently.
            raise AllowlistViolation(
                "refusing to finish this diagnostic turn: post_issue_comment was never called. "
                "Every turn must post either the next question or the completion response before "
                "finishing."
            )
        if no_changes_needed:
            # A real dispatch finding (Etapa 9 item 2): configure_intake against an
            # instance where bootstrap_instance already defaulted every status field
            # to github_issue correctly has nothing left to write. The workflow's
            # own "no diff = fail" guard predates this case and cannot tell a
            # legitimate no-op apart from an author that silently did nothing wrong
            # -- this explicit, phase-allowlisted signal (still independently
            # reviewed, see docs/claude-agent-pilot.md) is what lets the two be
            # told apart without weakening intake's existing "ambiguous/no
            # candidate must fail loudly" behavior, which never sets this flag.
            if self.phase not in PHASES_ALLOWING_NO_CHANGES_NEEDED:
                raise AllowlistViolation(
                    f"no_changes_needed is not available to phase {self.phase!r}; "
                    "write the required files instead"
                )
            if not reason.strip():
                raise AllowlistViolation("no_changes_needed=true requires a non-empty reason")
        self.finished = True
        self.finish_payload = {
            "summary": summary,
            "next_action": next_action,
            "no_changes_needed": bool(no_changes_needed),
            "reason": reason if no_changes_needed else "",
        }
        return "phase marked finished"

    def submit_review(self, review_yaml: str, status: str, blocking_findings: list[str]) -> str:
        if self.role != "reviewer":
            raise AllowlistViolation("submit_review is not available to this role")
        if status not in ("approved", "action_required"):
            raise AllowlistViolation(f"invalid review status: {status!r}")
        if status == "approved" and blocking_findings:
            raise AllowlistViolation("cannot submit status=approved with non-empty blocking_findings")
        self.finished = True
        self.finish_payload = {
            "review_yaml": review_yaml,
            "status": status,
            "blocking_findings": list(blocking_findings),
        }
        return "review recorded"

    def dispatch(self, name: str, tool_input: Mapping[str, Any]) -> str:
        if name == "read_file":
            return self.read_file(tool_input["path"])
        if name == "list_dir":
            return self.list_dir(tool_input.get("path", "."))
        if name == "compute_sha256":
            return self.compute_sha256(tool_input["path"])
        if name == "write_file":
            return self.write_file(tool_input["path"], tool_input["content"])
        if name == "finish_phase":
            return self.finish_phase(
                tool_input["summary"],
                tool_input["next_action"],
                tool_input.get("no_changes_needed", False),
                tool_input.get("reason", ""),
            )
        if name == "submit_review":
            return self.submit_review(
                tool_input["review_yaml"],
                tool_input["status"],
                tool_input.get("blocking_findings", []),
            )
        if name == "list_intake_issues":
            return self.list_intake_issues()
        if name == "read_github_issue":
            return self.read_github_issue(tool_input["number"])
        if name == "resolve_intake_candidates":
            return self.resolve_intake_candidates(
                tool_input["expected_headings"],
                tool_input.get("required_response_headings", []),
                tool_input.get("consent_heading", ""),
            )
        if name == "label_github_issue":
            return self.label_github_issue(tool_input["number"], tool_input["label"])
        if name == "unlabel_github_issue":
            return self.unlabel_github_issue(tool_input["number"], tool_input["label"])
        if name == "list_assessment_issues":
            return self.list_assessment_issues()
        if name == "resolve_assessment_candidates":
            return self.resolve_assessment_candidates(
                tool_input["topic_id"],
                tool_input.get("issue_number"),
            )
        if name == "apply_topic_assessment_result":
            return self.apply_topic_assessment_result(
                tool_input["topics"],
                tool_input["topic_id"],
                tool_input["passed"],
            )
        if name == "run_publish_projection":
            return self.run_publish_projection(
                tool_input["topics"],
                tool_input["operation_id"],
                tool_input["course_name"],
                tool_input.get("routine_mode", "none"),
            )
        if name == "list_issue_comments":
            return self.list_issue_comments(tool_input["number"])
        if name == "post_issue_comment":
            return self.post_issue_comment(tool_input["number"], tool_input["body"])
        raise AllowlistViolation(f"unknown tool: {name}")


def _github_issue_read_tools() -> list[dict[str, Any]]:
    """Read-only GitHub Issues tools, shared by both author_tools() and reviewer_tools()."""
    return [
        {
            "name": "list_intake_issues",
            "description": (
                "List open, non-PR issues carrying the intake discovery label in the instance "
                "repository (resolved from GITHUB_REPOSITORY, never user input). Returns "
                "summaries only (no body) -- use read_github_issue for one issue's full body."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "read_github_issue",
            "description": "Fetch one GitHub issue's full rendered body, title, labels and author, by number.",
            "input_schema": {
                "type": "object",
                "properties": {"number": {"type": "integer"}},
                "required": ["number"],
            },
        },
    ]


def _track_issue_read_tool() -> list[dict[str, Any]]:
    """Just read_github_issue, not the intake-scoped list_intake_issues.

    Etapa 6a: `track` needs to inspect one already-known authoritative task
    issue at a time (its external_id comes from state/integrations.json via
    read_file, not from any discovery-label listing), so only the second
    entry of _github_issue_read_tools() applies here.
    """
    return [_github_issue_read_tools()[1]]


def _evaluate_resolution_tools() -> list[dict[str, Any]]:
    """list_assessment_issues + resolve_assessment_candidates, shared by both roles.

    Etapa 6c: the reviewer must independently re-run the same deterministic
    resolution the author ran (instructions/55-evaluate-topic.md's
    'independently recompute ... the candidate issue resolution'), not trust
    the author's stated issue number -- so it gets the same two read-only
    resolution tools, just never the publish-side-effect tools
    (post_issue_comment/label_github_issue/unlabel_github_issue) that follow
    them in author_tools().
    """
    return [
        {
            "name": "list_assessment_issues",
            "description": (
                "List every open+closed issue carrying assessment:submitted in the "
                "instance repository. Returns summaries only (no body) -- use "
                "resolve_assessment_candidates to classify them, never read_github_issue "
                "plus your own judgment."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "resolve_assessment_candidates",
            "description": (
                "Deterministically resolve the assessment issue for one topic using the "
                "real scripts/assessment_resolution.py algorithm -- never classify "
                "candidates yourself and never pick an arbitrary newest issue. Pass "
                "issue_number only when the learner's command gave an explicit issue "
                "number ('...Avalie a issue #<número>.'); omit it for the standard "
                "command ('...Avalie minhas respostas.') to search instead. Already-"
                "recorded attempts and the last attempt's timestamp are resolved by the "
                "harness itself from state/assessments/<topic_id>/, not supplied by you."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "topic_id": {"type": "string"},
                    "issue_number": {"type": "integer"},
                },
                "required": ["topic_id"],
            },
        },
    ]


def _run_publish_projection_tool() -> dict[str, Any]:
    """Shared tool schema for run_publish_projection, used by publish and evaluate (6d).

    Etapa 6d: evaluate needs this exact same tool to move a mastered
    topic's authoritative task to Concluído -- same engine, same call
    shape, so the schema (and its extensive real-usage description) is not
    duplicated per phase.
    """
    return {
        "name": "run_publish_projection",
        "description": (
            "Run the real scripts/task_projection_engine.py projection and read-back "
            "validation against GitHub Issues -- never construct or validate the "
            "projection yourself. `topics` is a list of objects matching "
            "TopicProjection's fields (topic_id, lesson_number, title, "
            "direct_prerequisite_ids, content_version, canonical_state, materialized, "
            "external_id, lesson_url, practice_url, assessment_url, "
            "learning_summary, estimated_minutes, deliverable_summary, "
            "completion_criterion, session_checklist), read from the approved roadmap "
            "and topic contracts via read_file. learning_summary/estimated_minutes/"
            "deliverable_summary/completion_criterion/session_checklist populate the "
            "'O que você vai aprender'/'Tempo sugerido'/'O que você vai produzir'/'Para "
            "concluir'/'Sua sessão de estudo' sections instructions/40-publish-tasks.md "
            "requires on the rendered card -- read the real topic contract and module "
            "for these values, never leave them unset (session_checklist needs 3 to 7 "
            "granular actions from the module, not a generic placeholder). A topic's "
            "real URL may legitimately contain its own topic_id as a path segment "
            "(e.g. study/modules/TOPIC-001.md) -- the engine exempts a topic's own ID "
            "inside its own resource URL from the metadata-leak check, so pass the "
            "real URL rather than inventing a workaround. For every "
            "topic already published before, pass its known external_id from "
            "state/integrations.json so the engine updates the same issue instead of "
            "creating a duplicate. On status='success', write "
            "state/integrations.json, study/integrations.md and "
            "state/operations/<operation_id>.json from the returned payload. On "
            "status='error', do not write state/integrations.json or "
            "study/integrations.md -- persist only the operation journal (if present "
            "in the response) and report the blocked/partial outcome through "
            "finish_phase, per instructions/40-publish-tasks.md. `routine_mode` "
            "(optional, defaults to 'none') should be the real "
            "integration_preferences.routine.mode value from study.config.yml, read "
            "via read_file -- it appears verbatim in the generated "
            "study/integrations.md so scripts/integration_resolution.py's real "
            "validator can find it; the default only covers this pilot's single "
            "actual configuration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topics": {"type": "array", "items": {"type": "object"}},
                "operation_id": {"type": "string"},
                "course_name": {"type": "string"},
                "routine_mode": {"type": "string"},
            },
            "required": ["topics", "operation_id", "course_name"],
        },
    }


def author_tools(phase: str | None = None) -> list[dict[str, Any]]:
    finish_phase_properties: dict[str, Any] = {
        "summary": {"type": "string"},
        "next_action": {"type": "string"},
    }
    finish_phase_description = "Call once all required files are written, to end the author run."
    if phase in PHASES_ALLOWING_NO_CHANGES_NEEDED:
        finish_phase_properties["no_changes_needed"] = {
            "type": "boolean",
            "description": (
                "Set true only when you verified every requirement in this phase's "
                "instructions is already satisfied by the repository as it stands, so "
                "there is nothing to write. This does NOT skip review -- an independent "
                "reviewer still checks the repository directly and can reject this claim. "
                "Leave false (the default) whenever you write any file."
            ),
        }
        finish_phase_properties["reason"] = {
            "type": "string",
            "description": (
                "Required when no_changes_needed is true: which specific requirements you "
                "checked and how you confirmed each is already met. Ignored otherwise."
            ),
        }
        finish_phase_description += (
            " If, after checking, every requirement is already satisfied and nothing needs "
            "to change, call this with no_changes_needed=true and a reason instead of writing "
            "a no-op file just to have a diff."
        )
    tools = [
        {
            "name": "read_file",
            "description": "Read a UTF-8 text file from the repository, path relative to repo root.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        {
            "name": "list_dir",
            "description": "List entries of a directory, path relative to repo root.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": [],
            },
        },
        {
            "name": "write_file",
            "description": (
                "Write a UTF-8 text file, path relative to repo root. Only paths in the "
                "phase's allowed domain-output list are accepted; anything else is rejected."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "finish_phase",
            "description": finish_phase_description,
            "input_schema": {
                "type": "object",
                "properties": finish_phase_properties,
                "required": ["summary", "next_action"],
            },
        },
    ]
    if phase == "intake":
        tools.extend(_github_issue_read_tools())
        tools.append(
            {
                "name": "resolve_intake_candidates",
                "description": (
                    "Deterministically classify every open candidate issue using the real "
                    "scripts/intake_resolution.py algorithm -- never classify candidates "
                    "yourself. Pass expected_headings, required_response_headings and "
                    "consent_heading exactly as read from "
                    ".github/ISSUE_TEMPLATE/create-study-path.yml via read_file. "
                    "allowed_authors and already-imported references are resolved by the "
                    "harness itself from repository state, not supplied by you."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "expected_headings": {"type": "array", "items": {"type": "string"}},
                        "required_response_headings": {"type": "array", "items": {"type": "string"}},
                        "consent_heading": {"type": "string"},
                    },
                    "required": ["expected_headings"],
                },
            }
        )
        tools.append(
            {
                "name": "label_github_issue",
                "description": (
                    f"Apply a label to a GitHub issue. Only {INTAKE_AUTHOR_ALLOWED_LABEL!r} is "
                    "accepted -- call this only once, on the accepted candidate's issue number, "
                    "after every domain-output file has been written."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "label": {"type": "string"},
                    },
                    "required": ["number", "label"],
                },
            }
        )
    elif phase == "publish":
        tools.append(_run_publish_projection_tool())
    elif phase == "diagnostic":
        tools.append(
            {
                "name": "list_issue_comments",
                "description": (
                    "Read the full comment thread of the diagnostic session issue, in "
                    "chronological order. This is your only source of the running session state "
                    "-- you have no memory of earlier turns. Call this first, every turn, to "
                    "reconstruct exactly how many questions have been asked and what the "
                    "learner answered before deciding your next action."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {"number": {"type": "integer"}},
                    "required": ["number"],
                },
            }
        )
        tools.append(
            {
                "name": "post_issue_comment",
                "description": (
                    "Post one comment to the diagnostic session issue -- your only channel to "
                    "the learner. Use it once, in turn 1, to post the whole question set together "
                    "as a single numbered list (instructions/20-diagnostic.md's interaction style: "
                    "single form batch, not one question per turn, no separate transition "
                    "message), or for the single learner-facing completion response once you have "
                    "evaluated the reply, written the domain files and the repository operation is "
                    "done."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "body": {"type": "string"},
                    },
                    "required": ["number", "body"],
                },
            }
        )
    elif phase == "track":
        tools.extend(_track_issue_read_tool())
    elif phase == "evaluate":
        tools.extend(_evaluate_resolution_tools())
        tools.append(_github_issue_read_tools()[1])  # read_github_issue
        tools.append(
            {
                "name": "post_issue_comment",
                "description": (
                    "Post the detailed evaluation as a comment on the resolved assessment "
                    "issue. Etapa 6d note: instructions/55-evaluate-topic.md's own text says "
                    "not to publish until the independent assessment review has approved, but "
                    "this harness's author and reviewer are two separate isolated calls with "
                    "no step after the reviewer that could publish anything -- the same "
                    "precedent already established for intake's label write and publish's "
                    "issue writes: call this now, in the same author pass as your grading, "
                    "and the independent reviewer job plus the human merging the resulting PR "
                    "is what actually gates whether this run's conclusions stand, not a delay "
                    "of the write itself."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "body": {"type": "string"},
                    },
                    "required": ["number", "body"],
                },
            }
        )
        tools.append(
            {
                "name": "label_github_issue",
                "description": (
                    f"Apply a label to the resolved assessment issue. Only {GRADED_LABEL!r} "
                    f"(mastered) or {RECOVERY_REQUIRED_LABEL!r} (not mastered) is accepted -- "
                    "apply exactly one, after posting the evaluation comment, never both."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "label": {"type": "string"},
                    },
                    "required": ["number", "label"],
                },
            }
        )
        tools.append(
            {
                "name": "unlabel_github_issue",
                "description": (
                    f"Remove a label from the resolved assessment issue. Only "
                    f"{SUBMITTED_LABEL!r} is accepted -- remove it once grading is finalized, "
                    "per instructions/55-evaluate-topic.md's 'remove assessment:submitted "
                    "from the issue'."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "label": {"type": "string"},
                    },
                    "required": ["number", "label"],
                },
            }
        )
        tools.append(_run_publish_projection_tool())
        tools.append(
            {
                "name": "apply_topic_assessment_result",
                "description": (
                    "Etapa 6d: given the current `topics` list (same shape as "
                    "run_publish_projection's own `topics` parameter, read from the approved "
                    "roadmap and topic contracts), set the graded topic's canonical_state to "
                    "'completed' (passed=true, mastered) or 'review_required' (passed=false, "
                    "not mastered) and return the updated list. Call this before "
                    "run_publish_projection, never mutate canonical_state by hand in a "
                    "write_file call -- that bypasses run_publish_projection's own "
                    "idempotency and read-back validation."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "topics": {"type": "array", "items": {"type": "object"}},
                        "topic_id": {"type": "string"},
                        "passed": {"type": "boolean"},
                    },
                    "required": ["topics", "topic_id", "passed"],
                },
            }
        )
    return tools


def reviewer_tools(phase: str | None = None) -> list[dict[str, Any]]:
    tools = [
        {
            "name": "read_file",
            "description": "Read a UTF-8 text file from the repository, path relative to repo root.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        {
            "name": "list_dir",
            "description": "List entries of a directory, path relative to repo root.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": [],
            },
        },
        {
            "name": "compute_sha256",
            "description": (
                "Compute the real sha256 of a file's exact current bytes, path relative to "
                "repo root. Always use this for the 'artifacts[].sha256' fields in the review "
                "document -- never write a hex string from memory or estimation."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        {
            "name": "submit_review",
            "description": (
                "Submit the final review verdict matching templates/review.yml. "
                "status='approved' requires blocking_findings to be empty."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "review_yaml": {"type": "string"},
                    "status": {"type": "string", "enum": ["approved", "action_required"]},
                    "blocking_findings": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["review_yaml", "status"],
            },
        },
    ]
    if phase in PHASES_WITH_GITHUB_ISSUES and phase != "diagnostic":
        # Reviewer gets read-only issue access -- enough to independently
        # re-fetch the source issue and compare its rendered fields against
        # what the author normalized, but never label_github_issue: the
        # reviewer must never be able to cause the external side effect it is
        # supposed to be checking. `diagnostic` is deliberately excluded even
        # though it's in PHASES_WITH_GITHUB_ISSUES (for the author's
        # comment-thread access): instructions/20-diagnostic.md requires the
        # reviewer to "reconstruct each placement conclusion from the bounded
        # evidence recorded in the summary" alone, never the raw comment
        # thread -- giving it any issue-reading tool here would work against
        # that privacy/minimization requirement, even though these
        # particular tools only reach issue bodies, not comments.
        #
        # `track` gets only the narrow single-issue tool
        # (_track_issue_read_tool()), not the full intake-scoped bundle:
        # list_intake_issues filters by the intake discovery label, which has
        # nothing to do with the authoritative task issue the track reviewer
        # needs to re-check. `evaluate` is the same story: it needs
        # read_github_issue only, plus _evaluate_resolution_tools() added
        # below (list_assessment_issues/resolve_assessment_candidates), not
        # the intake-scoped bundle either.
        if phase == "track":
            tools.extend(_track_issue_read_tool())
        elif phase == "evaluate":
            tools.append(_github_issue_read_tools()[1])  # read_github_issue only
        else:
            tools.extend(_github_issue_read_tools())
    if phase == "evaluate":
        tools.extend(_evaluate_resolution_tools())
    return tools


def anthropic_transport(payload: Mapping[str, Any], api_key: str) -> dict[str, Any]:
    """Real HTTP transport. Kept dependency-free (urllib) like the rest of the repo's scripts."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic API error {error.code}: {detail}") from error


def _describe_tool_call(block: Mapping[str, Any]) -> str:
    """One short diagnostic line for a tool_use block, for AgentBudgetExceeded's log.

    Includes the path/number a call acted on when there is one, so the
    resulting sequence shows real progress (different paths each time) or a
    repeated/looping pattern (the same path or an error over and over) at a
    glance, without needing the full transcript.
    """
    name = block.get("name", "<unknown>")
    tool_input = block.get("input", {}) or {}
    detail = tool_input.get("path") or tool_input.get("number") or tool_input.get("operation_id")
    return f"{name}({detail})" if detail is not None else name


def _with_trailing_cache_breakpoint(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of `messages` with a cache_control breakpoint on the last content block.

    Anthropic's prompt caching reuses everything up to (and including) a
    cache_control breakpoint on a subsequent call, provided the prefix is
    byte-identical. In a tool-use loop the message list only ever grows by
    appending, so marking the *last* block on every outgoing request means
    each round's newly-added content becomes the next round's cached prefix
    -- the growing history is paid for once, not resent at full price on
    every one of MAX_TOOL_ITERATIONS round trips. Without this, a run's
    total input tokens scale roughly with the square of its round-trip
    count; with it, they scale roughly linearly.

    Only the outgoing copy is touched; the caller's own `messages` list,
    which the loop keeps appending to, is left without cache_control keys.
    """
    if not messages:
        return messages
    copied = [dict(message) for message in messages]
    last = copied[-1]
    content = last["content"]
    if isinstance(content, str):
        last["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
    elif isinstance(content, list) and content:
        content = [dict(block) for block in content]
        content[-1] = {**content[-1], "cache_control": {"type": "ephemeral"}}
        last["content"] = content
    return copied


def run_agent(
    *,
    root: Path,
    phase: str,
    role: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    api_key: str | None = None,
    transport: Callable[[Mapping[str, Any], str], dict[str, Any]] = anthropic_transport,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    github_request: RequestJson | None = None,
    github_repository: str | None = None,
) -> AgentRun:
    """Run one author or reviewer agent call to completion (or until the budget runs out).

    Returns an AgentRun with the full transcript for logging/debugging plus the
    structured finish_payload the caller (author -> commit+PR, reviewer ->
    state/reviews/*.yml) needs to act on.

    `github_request`/`github_repository` are only consulted when `phase` is in
    PHASES_WITH_GITHUB_ISSUES; every other phase ignores them, same as `role`
    ignoring `transport`'s implementation details.
    """
    if role not in ("author", "reviewer"):
        raise ValueError(f"unknown role: {role}")

    tools = RepoTools(
        root=root,
        phase=phase,
        role=role,
        github_request=github_request,
        github_repository=github_repository,
    )
    tool_schemas = author_tools(phase) if role == "author" else reviewer_tools(phase)
    max_iterations = max_tool_iterations_for(phase)

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    run = AgentRun(phase=phase, role=role, model=model)
    tool_call_log: list[str] = []

    # The system prompt is identical on every round trip of this loop, so it
    # gets its own permanent cache breakpoint -- separate from the messages
    # breakpoint above, which moves forward each round as the conversation grows.
    system_blocks = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]

    for _ in range(max_iterations):
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "messages": _with_trailing_cache_breakpoint(messages),
            "tools": tool_schemas,
        }
        response = transport(payload, api_key or "")
        run.transcript.append(
            {
                "role": "assistant_response",
                "content": response.get("content", []),
                "stop_reason": response.get("stop_reason"),
            }
        )
        if "usage" in response:
            run.usage.add(response["usage"])
        content = response.get("content", [])
        messages.append({"role": "assistant", "content": content})

        tool_use_blocks = [block for block in content if block.get("type") == "tool_use"]
        if not tool_use_blocks:
            break

        tool_results: list[dict[str, Any]] = []
        for block in tool_use_blocks:
            tool_call_log.append(_describe_tool_call(block))
            try:
                result_text = tools.dispatch(block["name"], block.get("input", {}))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result_text,
                    }
                )
            except (AllowlistViolation, KeyError) as error:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": str(error),
                        "is_error": True,
                    }
                )
        messages.append({"role": "user", "content": tool_results})
        run.transcript.append({"role": "tool_results", "content": tool_results})

        if tools.finished:
            break
    else:
        raise AgentBudgetExceeded(
            f"{role} agent for phase {phase!r} did not finish within {max_iterations} tool round trips",
            tool_call_names=tool_call_log,
        )

    run.finished = tools.finished
    run.finish_payload = tools.finish_payload
    run.files_written = tools.files_written
    return run


def _load_models_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {"version": 1, "reasoning_tier": "recommended", "model_overrides": {}}
    import yaml  # local import: keep base module dependency-free for tests

    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=["author", "reviewer"])
    parser.add_argument("--phase", required=True, choices=sorted(PHASE_ALLOWLISTS))
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--system-prompt-file", required=True)
    parser.add_argument("--user-prompt-file", required=True)
    parser.add_argument("--models-config", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Resolve the model and exit without calling the API")
    args = parser.parse_args(argv)

    config = _load_models_config(args.models_config)
    if args.role == "author":
        agent_id = PHASE_AUTHOR_AGENT[args.phase]
        model = resolve_effective_models(config)[agent_id].model
    else:
        model = resolve_phase_reviewer_model(args.phase, config)

    if args.dry_run:
        print(f"role={args.role} phase={args.phase} model={model}")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    github_request: RequestJson | None = None
    github_repository: str | None = None
    if args.phase in PHASES_WITH_GITHUB_ISSUES:
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            raise SystemExit(f"GITHUB_TOKEN is not set (required for phase {args.phase!r})")
        # Deliberately GITHUB_REPOSITORY, the Actions-provided identity of the
        # repository this workflow run belongs to -- never a CLI flag or
        # workflow_dispatch input. See the module docstring and
        # RepoTools._require_github for why that boundary matters.
        github_repository = os.environ.get("GITHUB_REPOSITORY")
        if not github_repository:
            raise SystemExit(f"GITHUB_REPOSITORY is not set (required for phase {args.phase!r})")
        github_api_url = os.environ.get("GITHUB_API_URL", GITHUB_API_URL_DEFAULT)
        github_request = github_request_factory(github_token, github_api_url)

    try:
        run = run_agent(
            root=Path(args.repo_root),
            phase=args.phase,
            role=args.role,
            model=model,
            system_prompt=_read_text(args.system_prompt_file),
            user_prompt=_read_text(args.user_prompt_file),
            api_key=api_key,
            github_request=github_request,
            github_repository=github_repository,
            max_tokens=max_tokens_for(args.phase),
        )
    except AgentBudgetExceeded as exc:
        # Without this, the only signal in the job log used to be "did not
        # call its finish tool" -- indistinguishable whether the agent made
        # real, varied progress that just needed more room, or was stuck
        # repeating the same call. Printed to stderr (visible in the Actions
        # log) before still failing the job the same way as before.
        print(f"::error::{exc}", file=sys.stderr)
        print("Tool calls made before the budget ran out:", file=sys.stderr)
        for index, call in enumerate(exc.tool_call_names, start=1):
            print(f"  {index:2d}. {call}", file=sys.stderr)
        raise SystemExit(1) from exc

    if not run.finished:
        # Same reasoning as the AgentBudgetExceeded diagnostics above, for
        # the other way a run can end without finishing: the model stops
        # producing tool_use blocks (so the loop breaks early, without
        # exhausting the iteration budget) without ever calling
        # finish_phase. stop_reason and any final text explain why --
        # e.g. "max_tokens" means the response was truncated mid-turn,
        # a model just stopping mid-plan looks different and points at a
        # prompt/behavior issue instead of a budget one.
        last_response = run.transcript[-1] if run.transcript else {}
        print(f"::error::{args.role} agent did not call its finish tool", file=sys.stderr)
        print(f"stop_reason: {last_response.get('stop_reason')}", file=sys.stderr)
        for block in last_response.get("content", []):
            if block.get("type") == "text":
                print(f"final text from the model:\n{block.get('text', '')}", file=sys.stderr)
        raise SystemExit(f"{args.role} agent did not call its finish tool")

    output = dict(run.finish_payload or {})
    output["model"] = model
    output["usage"] = run.usage.as_dict(model)
    print(json.dumps(output, indent=2))

    if run.files_written:
        print("files written:", ", ".join(run.files_written), file=sys.stderr)

    cost = run.usage.estimated_cost_usd(model)
    cost_str = f"${cost:.4f}" if cost is not None else "unknown (model not in local pricing table)"
    print(
        f"usage: {run.usage.input_tokens} input + {run.usage.output_tokens} output "
        f"+ {run.usage.cache_creation_input_tokens} cache-write + {run.usage.cache_read_input_tokens} cache-read "
        f"tokens -- estimated cost {cost_str} (model={model})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
