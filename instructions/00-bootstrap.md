# Bootstrap an instance

Bootstrap is allowed only in a fork or repository created from this template.

Read and apply `instructions/02-setup-execution.md` before inspecting or changing the target repository.

1. Read `AGENTS.md`, `.open-study-path/template.yml`, `.open-study-path/instance.yml` when present, `templates/instance.yml` and `instructions/manifest.yml`.
2. Resolve the exact target as `OWNER/REPOSITORY` from the explicit "Target repository" line every agent-pilot dispatch supplies (`docs/claude-agent-pilot.md`) or, absent that, an explicit repository identifier given directly.
3. Confirm the target is accessible and is not the canonical template repository.
4. Determine repository mode from the sentinel files, not repository size, search results or an incomplete local checkout. If `.open-study-path/template.yml` exists, the repository is not empty and its inherited infrastructure must be preserved.
5. If no explicit repository identifier is available anywhere in the initiating request, stop before writing and ask for the exact repository identifier.
6. Before writing generated setup artifacts, create one feature branch for the complete setup operation. Never write setup artifacts directly to the default branch.
7. If `.open-study-path/instance.yml` is absent, copy `templates/instance.yml`, replace `OWNER/REPOSITORY`, set the initialization timestamp and preserve its workflow defaults. Keep `.open-study-path/template.yml`; instance mode is represented by both markers, with the instance marker taking precedence.
8. New instances must start with `workflow.guided: true` and `workflow.intake_merge_policy: auto_when_unambiguous` unless the owner explicitly selects another supported policy.
9. If an instance marker already exists, verify its `repository` value matches the current target before writing anything. Do not overwrite an existing workflow policy silently.
10. Copy `study.config.example.yml` to `study.config.yml` and copy the state templates to their instance paths.
11. Copy `templates/integrations-state.json` to `state/integrations.json`, replace `OWNER/REPOSITORY`, and keep its resources empty. This file is only an idempotency index; it is not a second source of learning truth.
12. If `.open-study-path/models.yml` is absent, copy `templates/agent-models.yml` to `.open-study-path/models.yml` unchanged. Never overwrite an existing `.open-study-path/models.yml`. This is the optional per-agent reasoning-tier dial (`docs/agent-model-configuration.md`); shipping it with every override at its recommended default makes the dial discoverable and editable from the start instead of requiring the owner to find and copy the template manually later.
13. Leave all learner fields and provider selections unconfigured or `auto`. Do not import a submission, recommend providers or create external resources during bootstrap.
14. Continue to `instructions/05-configure-intake.md` unless the owner explicitly asks to postpone intake configuration.
15. Stop when the selected intake method is ready. Do not import answers, generate a curriculum, publish tasks or create study integrations during setup.
16. Assemble all outputs and the approved setup review on the same feature branch. Open exactly one pull request only after the complete setup head exists; intermediate commits must never be treated as a completed setup. **Exception:** when running under the isolated multi-agent harness (`docs/claude-agent-pilot.md`), the author does not assemble or self-approve a review artifact — a separate, independent reviewer call produces the one review that satisfies this step and the merge gate in `instructions/02-setup-execution.md`. A self-authored review in that mode would just be an unverified claim sitting next to the real one, which is worse than not having it.
17. Validate the complete setup diff and satisfy the merge gate in `instructions/02-setup-execution.md` before merging or reporting success.
18. Complete the phase using `instructions/phase-completion.md`, including the exact next action for the selected intake provider.

Repository identity always comes from an explicit statement in the request that triggers this phase, never from a chat product's own name, description or memory of an earlier message. After bootstrap, `.open-study-path/instance.yml` is the persistent repository and workflow source of truth. `study.config.yml` stores learner and capability preferences. `state/integrations.json` stores only safe external identifiers and synchronization metadata.

Never overwrite an existing instance without comparing changes. Setup must use one feature branch and one pull request for the complete first-chat operation.
