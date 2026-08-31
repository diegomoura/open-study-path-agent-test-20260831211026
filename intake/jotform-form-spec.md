# Jotform intake specification

The executable source of truth is [`jotform-form-spec.yml`](jotform-form-spec.yml). This document explains how an AI agent uses it.

## Ownership rule

Every Open Study Path instance that selects Jotform receives a new form in the instance owner's connected Jotform account. The canonical template does not contain a form ID and users do not need to duplicate a maintainer-owned form manually.

The generated form ID and URL belong only in the derived instance's `study.config.yml`.

## Automatic creation workflow

1. Set up a fork or derived repository as an instance.
2. Select `jotform` as the intake provider.
3. Confirm that the Jotform app is connected to ChatGPT.
4. When access is unavailable, ask the owner to authorize Jotform and stop. Never request an API key.
5. Check whether the instance already has an accessible `form_id`.
6. Search the owner's forms for an exact instance-specific title before creating a new form.
7. Read the complete YAML specification and translate it into the high-level natural-language request expected by the Jotform creation tool.
8. Create the form in the owner's personal workspace unless a team workspace was explicitly selected.
9. Save the returned form ID, URL, specification ID and version in `study.config.yml`.
10. Present the form URL and stop. Do not create a test submission or import answers during setup.

This process is idempotent: rerunning it must reuse a verified existing form instead of creating duplicates.

## Required questions

- Topic or skill to learn.
- Detailed objective.
- Current level: no knowledge, beginner, intermediate or advanced.
- Preferred content language.
- Available hours per week, validated as a positive number.
- Task manager: GitHub Issues, Trello or Markdown only.
- Consent to save normalized planning data without raw submissions or unnecessary personal data.

## Optional questions

- Name of the learning path.
- Concrete desired outcome.
- Motivation.
- Prior knowledge and experience.
- Deadline.
- Preferred days and periods.
- Learning formats.
- Theory/practice balance.
- Assessment style.
- Accessibility needs or restrictions.
- Google Calendar integration.
- Email summaries.
- Additional notes.
- Reference text or URLs.
- One or more file uploads.

## Optional attachments

File uploads must always be optional. Useful examples include a job description, résumé, PDF, syllabus, image or text file.

The agent should:

1. read an attachment only when it materially affects the plan;
2. avoid committing the original file;
3. save only safe metadata, a summary or a source reference;
4. continue without attachments when the written answers are sufficient.

## Submission selection

A submission is approved when the owner explicitly identifies it or asks the agent to use the latest submission. The agent must not silently combine multiple submissions.

## Normalization

The provider response is input, not the source of truth. Normalize it with [`field-mapping.yml`](field-mapping.yml) into `study.config.yml` and `state/intake-summary.json`. Raw responses and personal identifiers are not persisted by default.
