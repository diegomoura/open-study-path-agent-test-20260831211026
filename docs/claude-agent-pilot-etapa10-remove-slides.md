# Etapa 10 — remove study slides entirely

Status: **implemented**. Decided as part of the post-Etapa-9 handoff
alongside auto-merge (Opção C) and turning off default integration
suggestions -- see the handoff for the full decision context.

## Why remove instead of keep disabled by flag

Study slides had been off by default in this pilot since Etapa 5b
(`AGENT_PILOT_ENABLE_SLIDES`, unset/false), with a second, independent
switch in `instance.yml`'s `study_slides.enabled`. Keeping a feature behind
two toggles that both had to agree already caused at least two real bugs
found during the Etapa 9 end-to-end "Estoicismo" dispatch, fixed in PRs
#112 and #114: `generate_detailed` writing an inconsistent
`study_slides.enabled` value, and `publish` constructing a plausible-looking
but nonexistent slides URL for a pilot with slides off. This is exactly the
"two sources of truth that nobody tied together" pattern that has produced
real bugs elsewhere in this project. Since slide rendering
(`scripts/render_study_slides.mjs`, Node.js/Puppeteer/Mermaid) was never
actually wired into this harness in the first place -- the toggle only ever
gated a not-yet-built capability -- there was no working feature to
preserve behind a cleaner flag. Removing the code, the schema field, and
every conditional branch is strictly less risk than maintaining a
never-exercised path.

## What was removed

- Standalone scripts: `scripts/study_slides.py`,
  `scripts/study_slides_legacy.py`, `scripts/render_study_slides.mjs`,
  `scripts/test_study_slides.py`, `scripts/validate_study_slides.py`,
  `scripts/test_study_slide_renderer.mjs`,
  `scripts/update_static_svg_slide_contract_text.py`.
- `instructions/37-review-study-slides.md`, `docs/study-slides.md`,
  `templates/slide-review.yml`, and the whole `templates/study-slides/`
  directory.
- The `slides_url` field from `TopicProjection`
  (`scripts/task_projection_engine.py`) and every reference to it,
  including the `run_publish_projection` tool schema in
  `scripts/build_agent_prompt.py`.
- The `AGENT_PILOT_ENABLE_SLIDES` toggle and `slides_toggle_enabled()` in
  `scripts/agent_runtime.py`, including the loud refusal it used to raise
  in `main()`.
- The `slide_generator`/`slide_reviewer` agent rows from the model-tier
  configuration system (`schemas/agent-model-config.schema.json`,
  `scripts/agent_model_resolution.py`, `templates/agent-models.yml`,
  `docs/agent-model-configuration.md`) -- these were never-used rows for a
  capability that never shipped.
- All slide-conditional prose and steps across
  `instructions/28-propose-path.md`, `30-generate-path.md`,
  `32-generation-execution.md`, `36-review-course-content.md`,
  `38-complete-usable-generation.md` (the entire "visual readiness"
  completion dimension), `38-finalize-generated-bundle.md`,
  `40-publish-tasks.md`, `41-task-backend-projection.md`, and
  `57-materialize-next-content.md` (the densest file -- the whole
  "Independent study-slide review and rendering" section).
- `study_slides:` from `templates/instance.yml`'s schema, `slides`/
  `slides_pdf`/`slides_review` frontmatter fields from `templates/topic.md`,
  and the "Slides da aula" block from `templates/module.md`.
- `internal_slide_review`, `study/slides/`, and `state/slide-reviews/` from
  `instructions/manifest.yml`'s `generate` and `evaluate` phase outputs.
- All slide-specific CI steps from `.github/workflows/validate-template.yml`
  (contract-text migration, slide-contract detection, renderer cache/install,
  slide test/render/validate steps, the `study-slide-render-output`
  artifact upload) -- including the now-unused `Set up Node` step, since
  nothing left in the workflow runs Node.
- Two smaller, previously unlisted spots found only via a full-repo grep,
  not the original handoff: the `slides-link` operational block in
  `scripts/pedagogical_content_hash.py`, and `study/slides/` from
  `scripts/validate_instance_operation_scope.py`'s `CURRICULUM_PREFIXES`.

## What was deliberately left alone

Historical per-etapa docs (`docs/claude-agent-pilot-etapa4.md`,
`-etapa5.md`, `-etapa6-design.md`) still mention slides -- they are a
record of what was true when those etapas ran, not living configuration,
and are not rewritten after the fact. `docs/claude-agent-pilot.md` and
`docs/claude-agent-setup.md` were updated only where they described
*current* scope (the `generate_detailed` restriction row, the phase-scope
bullet list); their own historical narrative sections were left as
originally written where they describe a past dispatch's actual behavior
at the time.

## Validation

No real API dispatch was needed -- every check here is deterministic:
`python scripts/validate_template.py all`, all 25 `scripts/test_*.py`
scripts, and `python -m unittest discover tests/` (46 cases) all pass
after the removal, run from a clean clone of the branch before merge.
