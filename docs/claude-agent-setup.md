# Set up the agent pilot for an Open Study Path instance

Every `instructions/manifest.yml` phase runs as an isolated Claude API call
dispatched through GitHub Actions -- author and reviewer never share
context, and the workflow does the dispatching instead of a human copying
prompts into a chat conversation. This is the only onboarding path this
repository supports (Etapa 8 removed the earlier manual chat flow entirely).

Read `docs/claude-agent-pilot.md` for the full design rationale and current
validation status of every phase. This document is only the setup path:
what to add, where, and how to run it.

## Why this needs a Secret

The repository itself calls the Anthropic API directly from a GitHub
Actions workflow, so it needs its own credential: an `ANTHROPIC_API_KEY`
stored as a repository Secret. The workflow already lives in the repository
(it ships with the template) and reads `AGENTS.md` / `instructions/*.md`
directly at run time -- there is nothing to copy or paste anywhere. Setup
is the Secret plus one workflow run.

## Required repository Secret

`ANTHROPIC_API_KEY` -- add it under **Settings -> Secrets and variables ->
Actions** on the instance repository (the same repository the workflow will
run in, not a separate driver repository). This is never copied automatically
by the GitHub template generator -- every new instance, including disposable
test repositories, needs it added by hand.

Before running this against anything but a disposable test repository, set
a spend limit for that key in the Anthropic Console. Never put the key in a
committed file, an issue body, or a workflow log.

## Required repository setting: allow Actions to open pull requests

Every dispatched phase ends by having the workflow's own `GITHUB_TOKEN` open
a pull request. GitHub repositories created from a template do **not**
inherit this permission -- it defaults to off, and the first dispatch on a
fresh instance fails at the "Open pull request" step with `GitHub Actions is
not permitted to create or approve pull requests`.

Enable it once per instance, before the first dispatch: **Settings ->
Actions -> General -> Workflow permissions -> "Allow GitHub Actions to create
and approve pull requests"**. This is a repository security setting, not a
Secret -- it does not need to be kept confidential, but it is worth knowing
what it grants: the workflow's token can open (not merge) pull requests. This
pilot still never auto-merges (see "What this pilot deliberately does not do
yet" below); this setting only unblocks the PR-opening step every phase
already depends on.

## Setup steps

1. Create a repository from `diegomoura/open-study-path` using the GitHub
   template. The `agent-pilot-*.yml` workflows are already part of the
   template; nothing extra to copy in.
2. Add `ANTHROPIC_API_KEY` as a repository Secret (above) and set its spend
   limit in the Anthropic Console.
3. Enable "Allow GitHub Actions to create and approve pull requests" (above).
   Skipping this is the most common first-dispatch failure on a new instance.
4. Optional: if you want to override the recommended Claude model tier per
   agent role, edit `.open-study-path/models.yml` after your first
   `bootstrap_instance` run creates it from `templates/agent-models.yml` (see
   `docs/agent-model-configuration.md`). Leave every override `null` to use
   the recommended tier for every agent.
5. Go to the **Actions** tab -> **Agent pilot** -> **Run workflow**.
6. Choose `phase` from the dropdown (see "Current scope" for what each phase
   actually does today), and give `target_repo` as this same repository's
   `OWNER/REPOSITORY`. `extra_context` is optional free text passed straight
   to the author agent (a course name, a specific instruction, or -- for
   `evaluate` -- the learner's literal command, see `docs/claude-agent-pilot.md`).
7. The workflow opens a pull request with the author's diff and the
   independent reviewer's verdict (`state/reviews/agent-pilot-<phase>.yml`
   and a PR comment). Read the reviewer's findings before merging -- this
   pilot does not auto-merge; a human makes the final call on every run.

`diagnostic` does not use the Run workflow button: `instructions/20-diagnostic.md`
requires a real multi-turn placement conversation, so **Agent pilot -
diagnostic** instead triggers once per learner reply, on each comment posted
to the session issue. Start it by opening that issue; no separate dispatch
step.

## A pull request opened by a workflow does not trigger other workflows

GitHub does not run `pull_request`-triggered workflows (including
`validate-template.yml`, this repository's main CI) against a pull request
that was itself opened using the default `GITHUB_TOKEN` -- this is a
deliberate GitHub Actions safety limit against triggering infinite workflow
chains, not a bug in this repository. Every agent-pilot PR needs its CI
started by hand once: **Actions -> Validate Open Study Path -> Run workflow**,
choosing the PR's branch as `ref`. Do this before merging -- CI having a
green run against the PR's actual head commit is still the only thing that
justifies a merge; an automatically-triggered run is not a prerequisite, a
manually-triggered one satisfies it exactly the same way.

## Current scope

Every manifest phase now has a real, dispatchable path, but several carry
real restrictions -- read `docs/claude-agent-pilot.md` for the full detail
behind each one before relying on it:

| Phase | Restriction today |
|---|---|
| `bootstrap_instance`, `configure_intake` | `configure_intake` always resolves as `github_issue` intake; no interactive provider choice (nobody to ask in an unattended run) |
| `intake` | Only the `github_issue` provider path is wired; Jotform and manual YAML intake have no dispatched path yet |
| `publish` | Only the `task manager: GitHub Issues` backend; Trello/Todoist/Notion remain deferred |
| `generate_proposal`, `generate_detailed` | No slide generation -- study slides were removed from the pilot entirely, not just toggled off |
| `track`, `replan`, `evaluate` | No cross-repo restriction beyond the shared GitHub Issues scope above; `evaluate`'s materialization-on-mastery path reuses `generate_detailed`'s own restrictions |
| `diagnostic` | Its own event-triggered workflow, not `workflow_dispatch` -- see above |

None of these restrictions are enforced by hiding the option; each one fails
loudly (a tool call is rejected, or the author refuses) rather than silently
degrading. Jotform and manual YAML intake are documented contracts
(`docs/template-lifecycle.md`) waiting on a future stage to wire a dispatched
phase to them -- they are not deprecated, just not reachable yet.

## What this pilot deliberately does not do yet

- **No auto-merge.** Every run opens a pull request; a human merges it.
- **No fork trigger.** `workflow_dispatch` and `issue_comment` both require
  repository access to invoke -- there is no automated response to an
  external contributor's fork or PR.

See `docs/claude-agent-pilot.md`, "What this pilot deliberately does not do
yet," for the reasoning behind both.

## Cost visibility

Every run's combined author + reviewer token usage and estimated cost is
appended to `state/agent-pilot-usage.jsonl` in the instance repository and
shown in the pull request body. Treat the estimate as planning-only; check
the Anthropic Console for real billed usage. See `docs/claude-agent-pilot.md`,
"Token usage and cost estimates," for real sample numbers per phase.

## Updating an existing instance after a contract change

There is no separate copied-instructions file to go stale: the workflow
reads `AGENTS.md` and `instructions/*.md` directly from the instance
repository's own checkout on every run. Pulling in an upstream template
update (a normal git merge or cherry-pick from `diegomoura/open-study-path`)
is enough to bring the next dispatch up to date; there is no second
synchronization step.
