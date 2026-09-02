# Structural model-tier warning

Phase: `evaluate`. Configuration source: `.open-study-path/models.yml`.

One or more agents classified as structural (`scripts/agent_model_resolution.py`, `STRUCTURAL_AGENTS`) are configured below their recommended tier. This is not blocking -- it may be a deliberate cost/quality trade-off -- but it is recorded here so it is visible on this dispatch's pull request rather than silent.

- curriculum_architect is configured for 'sonnet', below its recommended tier ('opus') for a structural decision. Generated or reviewed content is likely to be less thorough than the default.
- curriculum_reviewer is configured for 'sonnet', below its recommended tier ('opus') for a structural decision. Generated or reviewed content is likely to be less thorough than the default.
