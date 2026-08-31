#!/usr/bin/env python3
"""Assemble the system/user prompt files consumed by scripts/agent_runtime.py.

Deliberately reads the real instruction files instead of duplicating their
text: `instructions/*.md` are the contract each phase already runs under, and
the point of stage 2 was that an API call reads the same contract a human
running a manual chat conversation used to read (proposal, section 2 -- "o
que não muda"). The manual chat path itself was later removed entirely
(Etapa 8), but this stays a thin assembler rather than a second copy of the
prose regardless -- there is still exactly one place, `instructions/*.md`,
that can drift out of date.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PHASE_INSTRUCTION_FILES = {
    "bootstrap_instance": ["instructions/00-bootstrap.md"],
    "configure_intake": ["instructions/05-configure-intake.md"],
    "intake": ["instructions/10-intake.md"],
    "publish": ["instructions/40-publish-tasks.md"],
    "generate_proposal": ["instructions/28-propose-path.md"],
    "generate_detailed": ["instructions/30-generate-path.md"],
    "diagnostic": ["instructions/20-diagnostic.md"],
    "track": ["instructions/50-track-progress.md"],
    "replan": ["instructions/60-replan.md"],
    "evaluate": [
        "instructions/55-evaluate-topic.md",
        # Etapa 6d: the "When the topic is mastered" -> auto-materialize
        # chaining path reuses these two contracts verbatim from
        # generate_detailed -- they are not evaluate-specific, but the
        # operative text for what run_publish_projection/materialization
        # must satisfy applies exactly the same way whether reached via
        # generate_detailed or evaluate's mastery path.
        "instructions/57-materialize-next-content.md",
        "instructions/38-finalize-generated-bundle.md",
    ],
}

# Files every author/reviewer prompt gets regardless of phase.
AUTHOR_CORE_SHARED_FILES = [
    "AGENTS.md",
    "instructions/phase-completion.md",
]

REVIEWER_CORE_SHARED_FILES = [
    "AGENTS.md",
    "instructions/04-review-generated-artifacts.md",
    "docs/review-framework.md",
    "templates/review.yml",
]

# Files beyond the core shared set, specific to one phase. Etapa 4 (proposal,
# section 7, step 4) is what first needed this split: instructions/
# 02-setup-execution.md defines the "Allowed setup diff" for the two setup
# phases specifically -- it is not the right contract to hand an `intake`
# author, which has its own domain-output list (see agent_runtime.py's
# INTAKE_ALLOWED_EXACT_PATHS) and its own completion-recovery contract.
PHASE_EXTRA_AUTHOR_FILES: dict[str, list[str]] = {
    "bootstrap_instance": ["instructions/02-setup-execution.md"],
    "configure_intake": ["instructions/02-setup-execution.md"],
    "intake": ["instructions/11-intake-completion-recovery.md", "intake/field-mapping.yml"],
    "publish": [
        "instructions/41-task-backend-projection.md",
        "instructions/42-integration-preflight.md",
        "docs/learner-facing-language.md",
    ],
    "generate_proposal": [
        "instructions/35-review-curriculum.md",
        "docs/learner-facing-language.md",
        "docs/beginner-first-pedagogy.md",
    ],
    "generate_detailed": [
        "instructions/36-review-course-content.md",
        "docs/learner-facing-language.md",
        "docs/beginner-first-pedagogy.md",
        "docs/content-quality-and-sources.md",
        "docs/mermaid-visual-learning.md",
        "docs/integration-capabilities.md",
    ],
    "diagnostic": ["instructions/21-diagnostic-completion-recovery.md"],
    # Etapa 6d: same materialization-quality context generate_detailed's
    # author already gets, since evaluate's mastery-triggered
    # materialization path produces the exact same kind of content and
    # must meet the exact same bar.
    "evaluate": [
        "docs/learner-facing-language.md",
        "docs/beginner-first-pedagogy.md",
        "docs/content-quality-and-sources.md",
        "docs/mermaid-visual-learning.md",
        "docs/integration-capabilities.md",
    ],
}

PHASE_EXTRA_REVIEWER_FILES: dict[str, list[str]] = {
    "intake": ["instructions/11-intake-completion-recovery.md", "intake/field-mapping.yml"],
    "publish": [
        "instructions/41-task-backend-projection.md",
        "instructions/42-integration-preflight.md",
    ],
    "generate_proposal": [
        "instructions/35-review-curriculum.md",
        "docs/beginner-first-pedagogy.md",
    ],
    "generate_detailed": [
        "instructions/35-review-curriculum.md",
        "instructions/36-review-course-content.md",
        "docs/beginner-first-pedagogy.md",
        "docs/content-quality-and-sources.md",
    ],
    "diagnostic": ["instructions/21-diagnostic-completion-recovery.md"],
    "evaluate": [
        "instructions/36-review-course-content.md",
        "docs/beginner-first-pedagogy.md",
        "docs/content-quality-and-sources.md",
    ],
}

# `review_profile` selects which required-check set instructions/
# 04-review-generated-artifacts.md applies (docs/review-framework.md,
# "Review profiles" table). Every phase before Etapa 4 used "setup"; intake
# uses its own profile with different required checks (request_fidelity,
# preference_preservation, ambiguity_resolution, data_minimization,
# next_phase_consistency -- instructions/11-intake-completion-recovery.md).
# `publish` uses the framework's `publication` profile name (not `publish` --
# docs/review-framework.md's table already used that name before this
# pilot existed). `generate_proposal` and `generate_detailed` both use
# `curriculum` -- the same profile manifest.yml assigns to the whole
# `generate` phase; two of its seven checks (content_review_complete,
# assessment_alignment) are about materialized content, which only exists
# once `generate_detailed` runs -- trivially satisfied ("nothing in scope")
# for `generate_proposal`, genuinely evaluated for `generate_detailed`.
# `diagnostic` uses its own profile (evidence_basis, bounded_questioning,
# adjacent_experience_separation, placement_consistency,
# privacy_and_minimization -- scripts/review_framework.py).
PHASE_REVIEW_PROFILE: dict[str, str] = {
    "bootstrap_instance": "setup",
    "configure_intake": "setup",
    "intake": "intake",
    "publish": "publication",
    "generate_proposal": "curriculum",
    "generate_detailed": "curriculum",
    "diagnostic": "diagnostic",
    "track": "progress",
    "replan": "replan",
    "evaluate": "assessment",
}

AUTHOR_HARNESS_NOTE = """\
## Runtime harness note (not part of the phase contract above)

You are being run as an isolated author agent for exactly one phase of the
Open Study Path lifecycle, through a minimal tool harness -- not a full shell.
You have exactly these tools:

- read_file(path): read one text file, path relative to repo root.
- list_dir(path): list one directory, path relative to repo root.
- write_file(path, content): write one text file. Only paths inside this
  phase's allowed domain-output list are accepted; anything else is rejected
  by the harness before it touches disk, regardless of what you request. Do
  NOT write a review artifact under `state/reviews/` yourself: the
  instruction contract you were given describes a single-context flow where
  the same conversation authors and reviews, but in this harness a separate,
  independent reviewer agent does that -- with no access to this
  conversation. A self-written review here would be an unverified claim
  sitting next to the real one.
- finish_phase(summary, next_action): call this exactly once, when every
  required output file has been written. Nothing you do after finish_phase
  runs. `next_action` should be the concrete next command the repository
  owner should give, in the tone of instructions/phase-completion.md's
  learner-facing response, not internal PR/CI detail.

There is no git access, no shell, no general network access from inside this
harness (some phases get a narrow, separately-described exception below). A
separate GitHub Actions step commits whatever you write, opens the pull
request, and a *separate* reviewer agent call -- with none of this
conversation in its context -- checks your work before anything merges.
"""

AUTHOR_INTAKE_TOOL_NOTE = """\
## Intake tool addendum (Etapa 4)

You additionally have narrow, read-mostly access to GitHub Issues in this
same repository, scoped to the intake discovery label:

- list_intake_issues(): summaries of open, non-PR issues carrying the
  discovery label. No body -- use read_github_issue for that.
- read_github_issue(number): one issue's full rendered body, title, labels,
  author.
- resolve_intake_candidates(expected_headings, required_response_headings,
  consent_heading): classifies every candidate using the real
  scripts/intake_resolution.py algorithm running in the harness, not your own
  judgment. Read expected_headings/required_response_headings/consent_heading
  from the checked-in `.github/ISSUE_TEMPLATE/create-study-path.yml` via
  read_file first, then pass them here. Do not attempt to decide which issue
  is the right one yourself before calling this -- that is exactly the
  "similarity or newest-issue heuristic" instructions/10-intake.md forbids.

  Real dispatch finding: this classifier does an exact, line-anchored string
  match against the rendered issue body, not a fuzzy or semantic one. Each
  heading you pass must be the literal Markdown GitHub renders for that
  field -- `### ` (heading level 3, one space) followed by the field's exact
  `label:` text from the YAML, verbatim: same wording, accents and
  punctuation, no trailing colon, no paraphrase. Passing a bare label without
  the `### ` prefix, or a label you reworded even slightly, makes every
  field built from it silently fail to match -- and because every field
  shares this exact same construction, one formatting slip fails all of them
  at once, which looks identical to a genuinely malformed submission. If
  `resolve_intake_candidates` rejects a candidate that a plain read of its
  rendered body looks complete and correct, re-derive each heading string
  character-for-character from the form YAML before concluding the
  submission itself is the problem.
  Trust this tool's `state` field (`unique`, `none`, or `ambiguous`) and act
  on `accepted`/`rejected` exactly as instructions/10-intake.md's Selection
  and import section describes for each state:
  - `unique`: proceed with the normal import -- write the three domain-output
    files, then call label_github_issue on the accepted candidate.
  - `none` or `ambiguous`: do **not** write any domain-output file, including
    `state/intake-summary.json`. That file is governed by the same allowed
    domain-output list as the other two and holds the canonical intake
    summary schema when (and only when) an import actually happened -- it is
    not a scratchpad for reporting a classification result. Report the
    outcome only through `finish_phase`'s `summary`/`next_action` fields: for
    `none`, return the direct form link as instructions/10-intake.md
    describes; for `ambiguous`, list each candidate's number, title and
    creation time and ask the owner to choose. Do not call
    label_github_issue in either case.
- label_github_issue(number, label): the only label you may ever pass here is
  `intake:imported`. Call it once, on the accepted candidate's issue number,
  only after every domain-output file has already been written -- this is a
  real, immediate write to the live repository, independent of whether the
  pull request you're producing is later merged.
"""

REVIEWER_HARNESS_NOTE = """\
## Runtime harness note (not part of the review contract above)

You are the independent reviewer for one already-completed author run. You do
not have and must not assume any of the author's reasoning -- only the diff
it produced and read access to the repository, exactly as
docs/review-framework.md requires ("the reviewer reconstructs evidence from
approved inputs, repository outputs ... it does not trust the authoring
pass's success claim").

Tools:

- read_file(path): read one text file, path relative to repo root.
- list_dir(path): list one directory, path relative to repo root.
- compute_sha256(path): compute the real sha256 of a file's exact current
  bytes. Always call this for every `artifacts[].sha256` value you put in the
  review document -- never write a hex string from memory or estimation. A
  fingerprint that isn't the real hash defeats the entire point of binding
  approval to exact bytes.
- submit_review(review_yaml, status, blocking_findings): call this exactly
  once. `review_yaml` must be a complete document matching the shape of
  templates/review.yml (contract_version, operation_id, phase, reviewer_role,
  independent_pass: true, status, artifacts with sha256 fingerprints, checks
  for every item in the phase's review profile, blocking_findings,
  non_blocking_findings). status='approved' is rejected by the harness unless
  blocking_findings is empty.

There is no git access, no shell, no general network access from inside this
harness (some phases get a narrow, separately-described exception below). The
workflow step after you records exactly the review you submit; it does not
edit it.
"""

REVIEWER_INTAKE_TOOL_NOTE = """\
## Intake tool addendum (Etapa 4)

You additionally have read-only access to GitHub Issues in this same
repository:

- list_intake_issues(): summaries of open, non-PR issues carrying the intake
  discovery label.
- read_github_issue(number): one issue's full rendered body, title, labels,
  author.

Use these to independently re-fetch the source issue the author claims to
have imported and compare it -- title, rendered field values, consent
checkbox, author, `intake:imported` label -- against what was normalized into
`study.config.yml` and `state/intake-summary.json`. You do not have
label_github_issue: you are checking whether the label was applied correctly,
not applying it yourself.
"""

AUTHOR_PUBLISH_TOOL_NOTE = """\
## Publish tool addendum (Etapa 4)

Restricted to the `github_issues` task-manager backend only in this pilot --
Trello, Todoist and any other provider are out of scope here (see
docs/claude-agent-pilot.md's Scope section). Do not attempt to resolve,
probe or write to any other task-manager provider, and do not activate
reminders, calendars or email -- this pilot only covers the required
task-manager capability.

You have exactly one tool for the actual publication:

- run_publish_projection(topics, operation_id, course_name): runs the real
  scripts/task_projection_engine.py projection, matching, external writes
  and read-back validation against GitHub Issues -- never build or validate
  the projection yourself. Read the approved roadmap and topic contracts via
  read_file first, then construct `topics` as a list of objects matching
  TopicProjection's fields (topic_id, lesson_number, title,
  direct_prerequisite_ids, content_version, canonical_state, materialized,
  lesson_url, practice_url, assessment_url). For every topic
  already published in an earlier run, read its known `external_id` from
  `state/integrations.json` first and pass it back in -- this is what lets
  the engine update the same issue instead of creating a duplicate.

  Also populate `learning_summary` (plain-language capability summary,
  becomes "O que você vai aprender:"), `estimated_minutes` (integer,
  becomes "Tempo sugerido:"), `deliverable_summary` (becomes "O que você
  vai produzir:"), `completion_criterion` (plain-language pass/scoring
  criterion, becomes "Para concluir:") and `session_checklist` (3 to 7
  granular actions taken from the module -- not a generic placeholder,
  becomes the "Sua sessão de estudo" checklist) for every topic, read from
  its real topic contract (`study/topics/<id>.md`) and module
  (`study/modules/<id>.md`). A real Etapa 6d dispatch's independent
  reviewer read a materialized card back from GitHub and found only a
  bare "Recursos" block and a generic 3-item checklist because these
  fields were left `None`/empty -- instructions/40-publish-tasks.md's
  "Ready lesson card" and "Future lesson card" sections require all of
  this content, and the engine now has fields for it but still needs the
  real values from the topic contract and module, not a placeholder.
  This also applies to a topic already moved to **Em estudo** by the
  learner -- it is the same materialized lesson, just moved, so populate
  these fields for it too, not only for topics still in Próxima aula/
  Disponível em paralelo. A real dispatch's reviewer caught a republish
  silently dropping this content for an in-progress topic.

  Call this tool exactly once per operation attempt. Its `journal` return
  value's `external_write_count` reflects only the writes made by *this*
  call, not the operation's cumulative history -- if you call it again
  after already getting a `status: "success"` response (to double-check
  the result, or because you are unsure something landed correctly), the
  second call's `preflight_match` will correctly find the resources it
  just created and skip writing them again, and *that* zero-write journal
  is what you will end up persisting, silently erasing the record that
  real writes happened at all. A real dispatch did exactly this and left
  `state/operations/<operation_id>.json` claiming zero external writes for
  an operation that had in fact created three real GitHub issues. On a
  `status: "success"` response, immediately do the three writes the next
  section describes and move on to `finish_phase` -- do not call
  `run_publish_projection` again to verify or re-check its own result.

  When a topic's real, materialized file paths happen to contain its own
  `TOPIC-000`-style ID (true for TOPIC-001, which predates the slug-
  filename convention `generate_detailed`/`evaluate` use for newer
  materializations), that is fine -- the engine's metadata-leak check now
  exempts a topic's own ID when it appears strictly inside its own
  resource URL, never for another topic's ID or a bare mention outside a
  URL. Do not invent a workaround (a placeholder URL, a null URL, or a
  made-up alternate path) to dodge this; a real Etapa 6d dispatch made 7
  increasingly strained attempts to route around what turned out to be a
  validator false positive, and every workaround either broke a different
  required check or produced a card with no working resource links at
  all. Pass the topic's actual, real URL, exactly as it exists in the
  repository.

The tool's response has a `status` field:

- `status: "success"`: write `state/integrations.json` (the returned
  `integration_state`, as JSON), `study/integrations.md` (the returned
  `learner_summary`, verbatim -- it is already validated, human-readable
  Markdown, do not rewrite it), and `state/operations/<operation_id>.json`
  (the returned `journal`, as JSON). Then call finish_phase with the
  completion response instructions/40-publish-tasks.md describes.
- `status: "error"`: do **not** write `state/integrations.json` or
  `study/integrations.md` -- the harness refuses those writes at the code
  level in this state regardless of what you attempt. If the response
  includes a `journal`, write only that to
  `state/operations/<operation_id>.json` (this is the resumable technical
  journal instructions/41-task-backend-projection.md requires even on a
  blocked or partial outcome). Report the blocked/partial/failed outcome
  through finish_phase using instructions/40-publish-tasks.md's guidance for
  that case -- do not claim success.
"""

REVIEWER_PUBLISH_TOOL_NOTE = """\
## Publish tool addendum (Etapa 4)

You have the same read-only GitHub Issues access as the intake reviewer
(list_intake_issues, read_github_issue) -- use it to independently re-fetch
the issues the author's `state/integrations.json` claims to have created or
updated, and compare title, labels and rendered description against what
instructions/40-publish-tasks.md and instructions/41-task-backend-
projection.md require (numbered title format, exactly one `Próxima aula`,
correct `study:*` label, no internal metadata leaked into visible fields).
For a ready lesson card, also confirm the body actually contains "O que
você vai aprender:", "Tempo sugerido:", "O que você vai produzir:", "Para
concluir:", the literal completion-command quote
(`**"Terminei <título da aula>. Avalie minhas respostas."**`) and a real
"Sua sessão de estudo" checklist with 3-7 granular items -- a bare
"Recursos" block plus a generic 3-item checklist is the exact structural
gap a real Etapa 6d dispatch's reviewer previously caught, so read the
actual issue body back rather than trusting that the author populated
these fields. You do not have run_publish_projection: you are checking
the result, not reproducing or re-running the publication.

Two things that read as inconsistencies but are not, on their own:

- `canonical_state` (in `internal_metadata`/`state/integrations.json`) and
  the visible GitHub label/column encode different axes. `canonical_state:
  "ready"` means the lesson's content is materialized -- it does not mean
  the lesson is eligible for the learner right now. A materialized topic
  whose prerequisites are not yet complete correctly has `canonical_state:
  "ready"` *and* label/visible_state `Planejado` at the same time; that is
  not a contradiction to flag. Only flag it if a topic's label/visible_state
  says `Próxima aula` or `Disponível em paralelo` while its prerequisites
  are genuinely still incomplete, or if canonical_state itself is invalid
  for the topic's real materialization status (e.g. `"ready"` on a topic
  that was never actually materialized).
- `state/operations/<operation_id>.json`'s `external_write_count` reflects
  only the author's *last* call to `run_publish_projection`, not the
  operation's full history -- a value of `0` on an otherwise-successful
  operation does not by itself mean nothing was written. Check the actual
  GitHub issues (which you have read access to) against `state/
  integrations.json`'s claims; that comparison, not the write-count number,
  is the real signal of whether the operation did what it claims.
"""

AUTHOR_PROPOSAL_NOTE = """\
## Proposal scope addendum (Etapa 5)

This run covers only the `proposal` suboperation of the `generate` phase
(instructions/28-propose-path.md) -- the roadmap architecture, nothing
materialized yet. instructions/28-propose-path.md already says this
explicitly, but it bears repeating given how much of the parent
instructions/30-generate-path.md's surrounding content (materialized
modules, assessments, rubrics) is reachable from the same
instructions/ directory: do not create `study/topics/`, `study/modules/`,
`study/assessments/`, `.github/ISSUE_TEMPLATE/assessment-
topic-*.yml`, or any other materialization artifact in this run. The only
files you may write are `study/roadmap.md` and `.open-study-path/
instance.yml` -- write_file rejects anything else regardless of what you
attempt, matching the same allowed-domain-output enforcement every other
phase in this harness already has.

Detailed content materialization (instructions/30-generate-path.md) is a
separate, not-yet-built harness phase -- do not attempt it here even if the
roadmap makes it tempting to keep going.
"""

REVIEWER_PROPOSAL_NOTE = """\
## Proposal scope addendum (Etapa 5)

You are reviewing only the `proposal` suboperation -- a roadmap architecture,
no materialized content. Two of the seven required `curriculum` profile
checks (`content_review_complete`, `assessment_alignment`) are about
materialized lessons and assessments that do not exist yet at this stage.
Record them as `passed` with a short note that there is no materialized
content in scope for this operation to fail those checks against -- do not
leave them `pending` (an incomplete review) and do not invent materialized-
content findings that don't apply.
"""

AUTHOR_DETAILED_NOTE = """\
## Detailed-generation scope addendum (Etapa 5b)

Everything in instructions/30-generate-path.md applies in full:
dependency-aware topic contracts, beginner-first concept progression,
outcome traceability via hidden markers, the source and provenance
contract, the 100-point rubric, the GitHub Issue Form per materialized
topic, and running instructions/36-review-course-content.md as the
independent content-review pass. Only materialize the deterministic
lookahead window from `.open-study-path/instance.yml`'s
`content_generation` config (or all topics, if the roadmap is within both
`full_upfront_max_topics` and `full_upfront_max_hours`) -- do not
materialize every future topic regardless of that budget.

REQUIRED DELIVERABLE, not an optional later step: for every topic you
materialize in this run, you must also produce and commit a passing
`state/content-reviews/<TOPIC-ID>.yml` from running instructions/36-review-
course-content.md yourself, in this same operation. A real dispatch (Etapa
5b validation, docs/claude-agent-pilot-etapa5.md section 7) produced an
otherwise-strong materialized topic but never created this file, and the
isolated reviewer correctly blocked the whole operation for it
(`action_required`) even though everything else passed -- do not repeat
that gap. Acknowledging the omission in your summary is not a substitute
for doing it.
"""

REVIEWER_DETAILED_NOTE = """\
## Detailed-generation scope addendum (Etapa 5b)

Apply instructions/36-review-course-content.md in full to every
materialized topic: outcome traceability, source and provenance checks,
beginner-first progression where the learner's level warrants it, and
whether the lookahead-window scope (not the whole roadmap) was respected.
"""

AUTHOR_DIAGNOSTIC_NOTE = """\
## Diagnostic session addendum (Etapa 4b, question style updated in Etapa 9c/9d)

This run is one turn of a two-turn session, not a single self-contained
operation -- you have no memory of earlier turns, and the same instruction
contract above was written assuming a live conversational chat. This
addendum adapts it to how this harness actually invokes you: triggered once
per learner reply (a GitHub issue comment), always a fresh process.

Every turn, in this order:

1. Call list_issue_comments(number) first, always -- this is your only
   record of the session. Reconstruct whether you have already posted the
   question batch (your own prior comment listing every question) and
   whether the learner has replied since. Never assume this is the first
   turn without checking.
2. If you have not yet posted the question batch: choose the question count
   from instructions/20-diagnostic.md's budget table (this is decided once,
   here, not extended turn by turn -- there is no second round of
   questions), then call post_issue_comment(number, body) with the entire
   numbered question list in one message, stating the total count up front.
   Also include, on its own line, a direct clickable link the learner can
   use instead of writing a comment by hand:
   `https://github.com/<owner>/<repo>/issues/new?template=diagnostic-answer.yml&session_issue_number=<this issue's number>`
   -- substitute the actual owner/repo (this transcript's target repository)
   and this session issue's own number (shown at the top of this
   transcript). Label it with something like **Responder pelo formulário**.
   Then call finish_phase with a summary noting the question count and
   next_action "waiting for the learner's reply" -- do NOT write
   state/diagnostic-summary.json or .open-study-path/instance.yml on this
   turn. Never post a separate "there is enough evidence, I will register
   it" transition comment, and never ask only part of the question set
   expecting a follow-up round.
   Exception: if this transcript's very first comment already contains
   complete, unprompted answers to what the question set would have asked,
   skip straight to step 3 in this same turn instead of posting a question
   batch at all.
3. Otherwise (the question batch is already posted and the learner has
   replied, whether by comment or via the linked form -- both arrive as an
   ordinary comment on this issue by the time you read it, see the bridge
   note below): evaluate the entire reply at once against every question
   you asked. This is always the terminal turn -- there is no third round.
   If the reply leaves a genuine gap on some dimension, do not ask a
   follow-up question; record evidence_sufficiency: limited and the gap as
   a material caveat instead, per instructions/20-diagnostic.md's stopping
   rule. Write state/diagnostic-summary.json and .open-study-path/instance.yml
   exactly as instructed above, then call post_issue_comment with the single
   learner-facing completion response (starting depth, and
   instructions/20-diagnostic.md's exact roadmap-proposal guidance for the
   next command) -- use instructions/21-diagnostic-completion-recovery.md's
   "provisional" language, since this comment is posted before the pull
   request this same operation opens is reviewed and merged. Then call
   finish_phase.

A learner who used the linked Issue Form instead of typing a comment never
appears to you as anything different: `.github/workflows/agent-pilot-diagnostic-answer-bridge.yml`
resolves and validates that form submission deterministically (never by your
judgment) and reposts its answers as a normal comment on this session issue
before you are ever invoked for it -- by the time list_issue_comments(number)
runs, it is just one more comment in the thread, formatted plainly, with no
special marker distinguishing it. Do not go looking for a separate answer
issue; you have no tool for that and are not meant to need one.

post_issue_comment automatically appends a hidden loop-prevention marker to
every comment it posts on your behalf -- you never need to add or think
about it yourself, it happens unconditionally.

finish_phase refuses to end a turn where post_issue_comment was never
called, in either case above -- a diagnostic turn must never end silently.
This does not check whether your sufficiency judgment itself was correct
(nothing can verify that mechanically); it only guarantees the learner
always gets a response.

Do not persist the raw transcript, the learner's literal answers, or any
comment thread content beyond what instructions/20-diagnostic.md's Output
section already asks you to record (competencies, gaps, starting depth,
etc.) -- state/diagnostic-summary.json holds conclusions, never a
transcript.
"""

REVIEWER_DIAGNOSTIC_NOTE = """\
## Diagnostic session addendum (Etapa 4b)

You review only the terminal turn -- the one that wrote
state/diagnostic-summary.json and .open-study-path/instance.yml and opened
a pull request. You have no tool access to the issue or its comment thread,
and that is deliberate: instructions/20-diagnostic.md requires you to
"reconstruct each placement conclusion from the bounded evidence recorded in
the summary" alone, never the raw transcript. If the summary's evidence
looks thin for the conclusion it reaches, that is itself a finding
(placement_consistency) -- do not try to look up the original conversation
to fill the gap.
"""


AUTHOR_TRACK_NOTE = """\
## Track tool addendum (Etapa 6a)

You may write only `state/progress.json` and `state/integrations.json` --
write_file rejects anything else regardless of what you attempt. This phase
never touches `study/`, `.open-study-path/instance.yml` or any content or
curriculum file; a structural pedagogical change belongs to replan, not
track.

You have one narrow GitHub tool: read_github_issue(number), for the already-
known authoritative task issue whose number comes from
`state/integrations.json` (via read_file), never from any discovery-label
listing -- you do not have list_intake_issues here, since that tool is
scoped to intake discovery, not task tracking. Use it to check the current
labels/state of the authoritative task issue before deciding the progress
transition.

Mastery only ever comes from a verified evaluation already recorded in
`state/assessments/` or an existing `state/progress.json` mastery entry --
never from this phase's own reading of task, reminder, habit, calendar or
formative-practice signals, exactly as instructions/50-track-progress.md's
"Activity completion is not equivalent to learning" section requires. If an
assessment issue exists but has not yet been evaluated, keep the topic in
the pending/`Em avaliação` state and surface the normal evaluate command
through finish_phase -- do not attempt to grade it yourself in this phase.

Every `state/integrations.json` resources[] entry has a fixed, managed
schema (see scripts/integration_resolution.py's ALLOWED_RESOURCE_KEYS). Do
not add any ad hoc field there to record study/practice/assessment activity
-- it will be rejected by the progress review, and even if it slipped
through, the next publish or evaluate republish would silently discard it
anyway, since the projection engine rebuilds every resource from scratch.
Record activity evidence only in `state/progress.json`.
"""

REVIEWER_TRACK_NOTE = """\
## Track tool addendum (Etapa 6a)

You have the same narrow read_github_issue(number) tool as the track author,
not the intake-scoped list_intake_issues bundle. Use it to independently
re-fetch the authoritative task issue's current state and verify that every
mastery value the author wrote traces back to an already-approved assessment
attempt or pre-existing progress entry, never to task/reminder/habit/
calendar signals alone (no_competing_authority, source_state_consistency).

Your `checks:` block must use these five keys verbatim -- copy them exactly,
do not paraphrase or invent a plausible-sounding synonym (a real Etapa 6a
dispatch got three of these wrong by paraphrasing, which fails CI even
though the review itself said "approved"):
`source_state_consistency`, `valid_state_transition` (singular),
`external_projection_consistency`, `next_action_consistency`,
`no_competing_authority`. If you are ever unsure whether a key you are about
to write is the literal one, read_file scripts/review_framework.py and copy
REVIEW_PROFILES["progress"]["checks"] directly rather than working from
memory or from docs/review-framework.md's prose description of what each
check covers.
"""


AUTHOR_REPLAN_NOTE = """\
## Replan tool addendum (Etapa 6b)

You may write only `.open-study-path/instance.yml`, `study.config.yml`,
`state/progress.json`, anything under `study/`, and
`.github/ISSUE_TEMPLATE/assessment-topic-*.yml` -- write_file rejects
anything else. This phase never touches `state/integrations.json` or
`state/assessments/`; an integration-projection or grading change belongs
to track or evaluate, not replan.

If `study.config.yml` is part of your change, read
`schemas/study-config.schema.json` first and match its shape exactly
(`version: 1`, the `configured`/`intake`/`planning` sections, English enum
values such as `beginner`/`balanced`, not free-text or another file's
schema). A real fixture in this pilot's disposable test repo drifted from
this schema for months before anyone caught it -- confirm your own diff
against the schema before finishing.

instructions/60-replan.md's "Migration boundary" section describes moving
state between repositories, providers or incompatible template contracts as
a *separate* operation with the `migration` profile -- that operation does
not exist in this harness yet. If the change you are asked to make requires
a task-backend or repository migration rather than a same-backend
replan, do not attempt it here: call finish_phase reporting that a
migration operation is required and out of scope for this dispatch, and
make no write_file calls.
"""

REVIEWER_REPLAN_NOTE = """\
## Replan tool addendum (Etapa 6b)

Your `checks:` block must use these five keys verbatim -- copy them
exactly from review_framework.py's REVIEW_PROFILES["replan"]["checks"]
rather than paraphrasing (a real Etapa 6a track dispatch got 3 of 5 keys
wrong this way before the addendum was corrected to spell them out):
`evidence_trigger`, `approved_scope_preservation`,
`dependency_revalidation`, `version_and_review_refresh`,
`learner_impact_explained`.

A curriculum or provider change that cannot be traced to a learner request,
changed constraint, diagnostic evidence or mastery result is a blocking
finding (evidence_trigger) -- do not approve a replan that looks plausible
but is not grounded in something persisted in the repository. If the diff
touches `study.config.yml`, also independently check it against
`schemas/study-config.schema.json`; a schema-shape drift is exactly the
kind of change dependency_revalidation and version_and_review_refresh
should catch even though neither check name mentions the config file by
name.
"""


AUTHOR_EVALUATE_NOTE = """\
## Evaluate tool addendum (Etapa 6d: grading, task-state move, materialization)

You may write `state/progress.json`, `state/integrations.json`,
`study/roadmap.md`, `study/integrations.md`, anything under
`state/assessments/`, `study/topics/`, `study/modules/`,
`study/flashcards/`, `study/assessments/`, and
`.github/ISSUE_TEMPLATE/assessment-topic-*.yml` -- write_file rejects
anything else.

Resolve the assessment issue with `resolve_assessment_candidates`, never by
reading `list_assessment_issues`/`read_github_issue` and judging candidates
yourself -- that tool decides *which* issue, not what to do with it. On
`state: "none"`, report that no submitted assessment was found via
finish_phase. On `state: "ambiguous"`, list only the candidate issue
numbers and links via finish_phase and stop -- do not guess. On
`state: "unique"`, call `read_github_issue` on that one accepted issue
number to get the actual submitted answers -- `resolve_assessment_candidates`
only returns the classification decision (accepted/rejected + reasons),
never the issue body itself. Grade only from what `read_github_issue`
returns; do not proceed to scoring without it.

Never grade from checklist completion, task state, reminders, habit
streaks, calendar attendance or a formative quiz/flashcard score --
`instructions/55-evaluate-topic.md` is explicit that none of those are
sufficient mastery evidence by themselves. Grade only the resolved
assessment issue's actual answers against the rubric.

Publish as soon as grading and the task-state/materialization steps below
are complete, in this same pass -- do not withhold `post_issue_comment`/
`label_github_issue`/`unlabel_github_issue` waiting for a later step that
does not exist in this harness. The independent reviewer job plus the
human merging the resulting PR is what actually gates whether this run's
conclusions stand.

### If the topic is NOT mastered

Persist the attempt under `state/assessments/<topic_id>/`, prepare the
`state/progress.json` transition, apply `assessment:recovery-required`,
remove `assessment:submitted`, post the comment explaining the gap.

`instructions/55-evaluate-topic.md`'s "Synchronize derived providers"
section ("Move or complete the authoritative task backend according to
the GitHub result") applies regardless of mastery outcome, not only when
mastered -- a real Etapa 6d dispatch's reviewer correctly caught this
being skipped entirely, leaving the authoritative task issue showing a
stale "concluded" label/body while `state/progress.json` recorded
`review_required`, a visible contradiction. Do not skip it: build the
`topics` list the same way as the mastered path, call
`apply_topic_assessment_result(topics, topic_id, passed=false)` (sets
`canonical_state` to `review_required`, not `completed`), then call
`run_publish_projection` with the result so the authoritative task's real
label/body reflect the recovery outcome. Handle a `status="error"` result
the same way as the mastered path: no `study/`, `state/integrations.json`
or `study/integrations.md` writes, report via `finish_phase`.

`instructions/55-evaluate-topic.md`'s "Recovery and focused reassessment"
section also calls for creating a dedicated focused-recovery GitHub issue
(targeted study tasks, reassessment scoped to weak areas,
`RECOVERY-<topic_id>-A<attempt>` tracked in the task backend, linked to
the original assessment/module/task). This harness slice has no tool that
creates a new GitHub issue -- only `post_issue_comment` (comments on an
issue that already exists) and `label_github_issue`/`unlabel_github_issue`
(labels on an issue that already exists). Do not fabricate this by
commenting a "recovery issue" body onto the original assessment issue
instead of a real new one, and do not invent a `create_github_issue` call
that does not exist in your tool list. Complete the task-state sync above,
then report through `finish_phase` that focused-recovery-issue creation
is not enabled in this harness slice yet, so a human knows a real GitHub
issue for the recovery plan still needs to be opened by hand.

### If the topic IS mastered

1. Persist the attempt, prepare the `state/progress.json` mastery
   transition, apply `assessment:graded`, remove `assessment:submitted`,
   post the comment.
2. Read the current roadmap and topic contracts via `read_file` to build
   the `topics` list `run_publish_projection` expects (same shape
   `publish`'s own author already builds), including every already-known
   `external_id` from `state/integrations.json` so the engine updates
   existing issues instead of duplicating them.
3. Call `apply_topic_assessment_result(topics, topic_id, passed=true)` to
   get the updated list with this topic's `canonical_state` set to
   `completed` -- never hand-edit `canonical_state` in a `write_file` call
   instead.
4. Materialize the next topic in the rolling window per
   `instructions/57-materialize-next-content.md` and
   `38-finalize-generated-bundle.md` -- the same content bar
   `generate_detailed` already applies (beginner-first pedagogy, sourced
   content, Mermaid diagrams, no placeholder text). `lesson_url`
   must be a real, working link to the actual materialized module in this
   repository -- never a placeholder domain. A real Etapa 6d dispatch
   published a task card whose "Aula" link was a literal
   `https://example.com/...` URL leading nowhere, because an earlier
   version of this addendum's own illustrative example used that domain
   and was taken literally instead of as shape-only guidance. Use
   `https://github.com/<target repository>/blob/main/<path>`, pointing at
   the module file you just wrote.

   Never put the literal internal `topic_id` string (e.g. `TOPIC-002`)
   inside a `lesson_url`/`assessment_url` value -- a separate real Etapa
   6d dispatch hit `run_publish_projection` failing read-back validation
   for exactly this (the visible-content leak detector correctly treats
   an internal ID appearing in a rendered resource URL as a metadata leak,
   the same rule that already applies to descriptions). Since the real
   blob URL above necessarily contains the module's file path, save the
   materialized module itself under a slug filename derived from the
   topic's title (e.g. `study/modules/tipos-tipagem-estatica-e-erros.md`),
   not `study/modules/<topic_id>.md` -- the slug satisfies both
   requirements at once: a real, dereferenceable link, with no internal ID
   substring anywhere in it.

   Also write `state/content-reviews/<new_topic_id>.yml`, the content-review
   artifact `36-review-course-content.md` requires for any newly
   materialized topic (matching the one already committed for TOPIC-001)
   -- materializing content and presenting it as ready without that
   review is a blocking finding, not optional.
   `scripts/course_content_review.py`'s real validator requires the
   `review_mode` field to be the exact literal string `independent_pass`
   and the `status` field to be the exact literal string `approved` --
   nothing else validates, no matter how accurately it describes reality.
   A real Etapa 6d dispatch wrote `review_mode: same_pass_author_self_check`
   to be honest about not being a genuinely separate pass, and that alone
   would fail CI outright, before the check even gets to content quality.
   Write the two fixed field values exactly as required; honesty about
   this pass not being genuinely independent belongs only in prose, inside
   a `non_blocking_findings` entry -- never in a structured field the
   schema checks verbatim. Only write `status: approved` at all if the
   content genuinely meets every one of the 9 required checks at the same
   bar `generate_detailed`'s separate `content_reviewer` agent holds it
   to, since this is the only artifact claiming that check happened. Add
   the `non_blocking_findings` entry stating plainly that this review was
   written in the same turn as the content itself, not by a genuinely
   separate isolated call the way `generate_detailed`'s `content_reviewer`
   is -- the real independent check for this materialization is the
   separate evaluate reviewer job's own `next_materialization_consistency`
   inspection, not this file.

   `course_content_review.py`'s real validator deterministically
   cross-checks two things the LLM review pass can miss: each outcome
   marker (`LO-1`, `LO-2`, ...) must appear in the module exactly once,
   never repeated; and `state/content-reviews/<new_topic_id>.yml`'s own
   `outcome_coverage[].assessment_questions` for each outcome must exactly
   match that outcome's real `assessed_by` question list in
   `study/assessments/<new_topic_id>.yml` -- not an approximation, not a
   subset. A real Etapa 6d dispatch got full LLM-reviewer approval with a
   repeated `LO-4` marker and two stale `assessment_questions` lists, and
   still failed this deterministic check. Before finishing, read the
   assessment file you just wrote and verify the content-review's
   `outcome_coverage` matches it question-for-question, and grep the
   module for each outcome marker to confirm it appears exactly once.
5. Read `study.config.yml`'s `integration_preferences.routine.mode` value
   via `read_file`, then call `run_publish_projection` with the updated
   `topics` list (including the newly materialized topic,
   `materialized: true`, `canonical_state` reflecting its real readiness)
   and that real `routine_mode` value, so the real engine projects both
   the completed task and the newly available one to GitHub Issues in one
   pass and the generated `study/integrations.md` records the actual
   configured routine mode (required verbatim by
   `scripts/integration_resolution.py`'s real validator). Call
   `run_publish_projection` exactly once for
   this operation attempt: its `journal` return value's
   `external_write_count` reflects only that one call, not this
   operation's full history, and a real `publish` dispatch that
   re-invoked the tool after already getting `status: "success"` ended up
   persisting a second, idempotent, zero-write journal that silently
   erased the record that real writes had happened at all. On
   `status="success"`, write `state/integrations.json` and
   `study/integrations.md` from the returned payload, and update
   `state/progress.json`'s entry for the newly materialized topic to set
   its own `external_task` (`provider`, `external_id`, `last_synced_at`)
   from that same response -- a real Etapa 6d dispatch left this `null`
   while `state/integrations.json` and the live GitHub issue already
   showed a real created task, an internal disagreement between the two
   files that risks a duplicate task on the next publish/track run. Match
   the same `external_task` shape already used for the graded topic's own
   entry. On `status="error"` (ambiguous match, partial write, failed
   read-back), do not write those two files -- persist only the operation
   journal if present and report the blocked outcome through
   `finish_phase`, exactly as `instructions/40-publish-tasks.md` already
   requires of `publish`.
"""

REVIEWER_EVALUATE_NOTE = """\
## Evaluate tool addendum (Etapa 6d)

Your own `artifacts:` list must include `state/operations/*.json` if this
operation changed one -- `review_framework.py`'s
`phase_allows_artifact("assessment", ...)` now covers that path prefix
(diegomoura/open-study-path PR #115; it did not before, and omitting it
was correct until then). It must still NOT include
`state/content-reviews/*.yml` paths, even though they are real files this
operation legitimately changed: that prefix is deliberately excluded from
`is_generated_artifact()` entirely (validated instead by its own
dedicated contract, `scripts/course_content_review.py`), so it needs no
review coverage at all and never will, unlike the operations journal.
List every other real artifact this operation changed as usual.

Your `checks:` block must use these six keys verbatim -- copy them exactly
from `review_framework.py`'s `REVIEW_PROFILES["assessment"]["checks"]`
rather than paraphrasing (a real Etapa 6a track dispatch got 3 of 5 keys
wrong this way before its addendum was corrected to spell them out):
`submission_resolution`, `rubric_fidelity`, `independent_scoring`,
`feedback_alignment`, `progress_update`, `next_materialization_consistency`.

Keep the `checks:` block self-consistent with `blocking_findings`: a check
marked `failed` needs at least one `blocking_findings` entry explaining
why, and `status: action_required` needs at least one `failed` check
behind it -- a real Etapa 6d dispatch marked `next_materialization_consistency:
failed` with an empty `blocking_findings: []` and every other piece of its
own reasoning actually supporting "passed," which failed CI outright on a
self-contradiction alone (`validate_review_framework.py` requires every
listed check to equal `passed`, regardless of whether findings explain
the deviation). If your own investigation found nothing wrong, mark the
check `passed`.

Independently re-run `resolve_assessment_candidates` yourself -- do not
trust the author's stated issue number for `submission_resolution`. Re-score
every response against the rubric yourself for `independent_scoring` --
comparing the author's reasoning against each rubric criterion, not just
checking its arithmetic; a disagreement in scoring is a blocking finding,
not a note.

`progress_update`: the authoritative task's real state must reflect the
graded outcome regardless of mastery -- `55-evaluate-topic.md`'s
"Synchronize derived providers" section is not gated on mastery. Whether
mastered or not, confirm `apply_topic_assessment_result` +
`run_publish_projection` were actually called (not skipped, not
hand-edited) and that the real task issue's label/body genuinely changed
to match (`Concluído` when mastered, `Revisão necessária` when not). A
real Etapa 6d dispatch's reviewer correctly caught exactly the failure
mode to watch for here: grading persisted correctly in
`state/assessments/`/`state/progress.json`, but the live task issue was
never resynced, leaving it visibly contradicting the graded result. Also
confirm that when NOT mastered, the author reported (via `finish_phase`,
not fabricated) that this harness slice has no tool to create the
dedicated focused-recovery GitHub issue `55-evaluate-topic.md`'s
"Recovery and focused reassessment" section calls for -- a comment posted
onto the *original* assessment issue pretending to be that recovery issue
is a blocking finding, not an acceptable substitute.

`next_materialization_consistency`: when the topic is not mastered, this
check covers only the next-topic materialization step specifically (not
the task-state sync, which `progress_update` above covers) -- confirm the
author did not touch `study/` and did not attempt
`57-materialize-next-content.md`, since there is nothing to materialize
without mastery. When the topic *is* mastered, verify all of: the
authoritative task's `canonical_state` was actually moved via the real
engine (not hand-edited); `state/content-reviews/<new_topic_id>.yml` is
present, claims `status: approved`, and honestly discloses in a
`non_blocking_findings` entry that it was written in the same pass as the
content (that disclosure is expected and correct, not itself a finding --
do not block on it); the newly materialized topic itself genuinely meets
the same bar `36-review-course-content.md` already holds `generate_detailed`
to (outcome markers actually beside the content that teaches each one --
not beside a restatement of the objective, a real Etapa 6d dispatch's own
mistake this exact check is meant to catch -- sourced content, Mermaid
diagrams, no placeholder text, no literal internal
`topic_id` string inside any resource URL); and `run_publish_projection`'s
real read-back validation actually passed (check
`state/integrations.json`/`study/integrations.md` were written from a
`status="success"` result, not fabricated). You are the genuinely
independent check this materialization depends on -- re-verify the
content-review file's own claims yourself against the actual module text
rather than trusting them, since it was written in the same pass as the
content it is reviewing. A materialization that skips content review
entirely, misplaces outcome markers, leaks an internal ID into a resource
URL, or a task-state move that never called the real engine, is a
blocking finding here, not a documented scope boundary -- Etapa 6d has
both tools, so using them correctly is now in scope.
"""


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _diff_against(base_sha: str) -> str:
    result = subprocess.run(
        ["git", "diff", f"{base_sha}...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def build_author_prompts(phase: str, target_repo: str, extra_context: str) -> tuple[str, str]:
    sections = [_read(path) for path in AUTHOR_CORE_SHARED_FILES]
    sections.extend(_read(path) for path in PHASE_EXTRA_AUTHOR_FILES.get(phase, []))
    sections.extend(_read(path) for path in PHASE_INSTRUCTION_FILES[phase])
    sections.append(AUTHOR_HARNESS_NOTE)
    if phase == "intake":
        sections.append(AUTHOR_INTAKE_TOOL_NOTE)
    elif phase == "publish":
        sections.append(AUTHOR_PUBLISH_TOOL_NOTE)
    elif phase == "generate_proposal":
        sections.append(AUTHOR_PROPOSAL_NOTE)
    elif phase == "generate_detailed":
        sections.append(AUTHOR_DETAILED_NOTE)
    elif phase == "diagnostic":
        sections.append(AUTHOR_DIAGNOSTIC_NOTE)
    elif phase == "track":
        sections.append(AUTHOR_TRACK_NOTE)
    elif phase == "replan":
        sections.append(AUTHOR_REPLAN_NOTE)
    elif phase == "evaluate":
        sections.append(AUTHOR_EVALUATE_NOTE)
    system_prompt = "\n\n---\n\n".join(sections)

    user_prompt = (
        f"Target repository: {target_repo}\n"
        f"Phase: {phase}\n\n"
        f"{extra_context}\n\n"
        "Read whatever repository files you need through read_file/list_dir, then "
        "write only the files required by this phase's contract, then call finish_phase."
    )
    return system_prompt, user_prompt


def build_reviewer_prompts(phase: str, target_repo: str, base_sha: str, author_summary: str) -> tuple[str, str]:
    sections = [_read(path) for path in REVIEWER_CORE_SHARED_FILES]
    sections.extend(_read(path) for path in PHASE_EXTRA_REVIEWER_FILES.get(phase, []))
    sections.append(REVIEWER_HARNESS_NOTE)
    if phase == "intake":
        sections.append(REVIEWER_INTAKE_TOOL_NOTE)
    elif phase == "publish":
        sections.append(REVIEWER_PUBLISH_TOOL_NOTE)
    elif phase == "generate_proposal":
        sections.append(REVIEWER_PROPOSAL_NOTE)
    elif phase == "generate_detailed":
        sections.append(REVIEWER_DETAILED_NOTE)
    elif phase == "diagnostic":
        sections.append(REVIEWER_DIAGNOSTIC_NOTE)
    elif phase == "track":
        sections.append(REVIEWER_TRACK_NOTE)
    elif phase == "replan":
        sections.append(REVIEWER_REPLAN_NOTE)
    elif phase == "evaluate":
        sections.append(REVIEWER_EVALUATE_NOTE)
    system_prompt = "\n\n---\n\n".join(sections)

    review_profile = PHASE_REVIEW_PROFILE.get(phase, "setup")
    diff = _diff_against(base_sha)
    user_prompt = (
        f"Target repository: {target_repo}\n"
        f"Phase under review: {phase}\n"
        f"Review profile: {review_profile}\n\n"
        f"IMPORTANT: your review artifact's own top-level `phase:` YAML field "
        f"must be set to {review_profile!r} (the Review profile above), NOT "
        f"{phase!r} (the Phase under review above) -- review_framework.py's "
        f"REVIEW_PROFILES dict is keyed by profile names like 'assessment' and "
        f"'publication', not harness phase names like 'evaluate' and "
        f"'publish'. Confirmed by a real dispatch: a real evaluate review "
        f"used `phase: evaluate` and failed CI with 'unknown review phase: "
        f"evaluate' -- and the same mistake was found, already merged and "
        f"undetected until now, in a much earlier publish review that used "
        f"`phase: publish` instead of `phase: publication`. Get this field "
        f"right the first time.\n\n"
        f"Author's self-reported summary (untrusted, verify independently):\n{author_summary}\n\n"
        f"Diff produced by the author agent (base {base_sha} -> HEAD):\n"
        f"```diff\n{diff}\n```\n\n"
        "Reconstruct evidence for each required check from the diff and repository "
        "reads, then call submit_review exactly once."
    )
    return system_prompt, user_prompt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=["author", "reviewer"])
    parser.add_argument("--phase", required=True, choices=sorted(PHASE_INSTRUCTION_FILES))
    parser.add_argument("--target-repo", required=True)
    parser.add_argument("--out-system", required=True)
    parser.add_argument("--out-user", required=True)
    parser.add_argument("--extra-context", default="")
    parser.add_argument(
        "--extra-context-file",
        default=None,
        help=(
            "Path to a file whose content is used as extra_context instead of --extra-context. "
            "Needed for diagnostic: a multi-turn transcript can contain quotes/newlines that are "
            "unsafe to pass as a single shell argument, the same reasoning EXTRA_CONTEXT already "
            "follows via env: in the workflow YAML for --extra-context."
        ),
    )
    parser.add_argument("--base-sha", default=None, help="required for role=reviewer")
    parser.add_argument("--author-summary-file", default=None, help="required for role=reviewer")
    args = parser.parse_args()

    extra_context = args.extra_context
    if args.extra_context_file:
        extra_context = Path(args.extra_context_file).read_text(encoding="utf-8")

    if args.role == "author":
        system_prompt, user_prompt = build_author_prompts(args.phase, args.target_repo, extra_context)
    else:
        if not args.base_sha:
            raise SystemExit("--base-sha is required for role=reviewer")
        author_summary = ""
        if args.author_summary_file:
            author_summary = Path(args.author_summary_file).read_text(encoding="utf-8")
        system_prompt, user_prompt = build_reviewer_prompts(args.phase, args.target_repo, args.base_sha, author_summary)

    Path(args.out_system).write_text(system_prompt, encoding="utf-8")
    Path(args.out_user).write_text(user_prompt, encoding="utf-8")


if __name__ == "__main__":
    main()
