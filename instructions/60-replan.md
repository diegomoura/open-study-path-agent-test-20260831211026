# Replan

Recalculate schedule projections when availability, deadline or actual velocity changes. Preserve completed evidence and topic dependencies. Add, remove or split topics only when the goal, diagnostic evidence or mastery results justify the change.

Document material curriculum changes in `study/roadmap.md` with date, reason and impact.

Re-evaluate `study/integrations.md` only when the changed course structure, availability, learner preference, provider access or repeated evidence creates a concrete new capability need. Do not rotate providers merely because another app exists.

Examples of justified integration changes:

- switch Trello to Todoist when a replanned path becomes short and simple;
- add reminder-only Todoist when spaced review becomes important;
- select Reclaim when schedule variability becomes the main blocker;
- add Habitify when consistency, rather than understanding, is repeatedly failing;
- add Quizlet when later topics introduce substantial atomic recall material;
- remove an unavailable or paid-only optional provider and retain its fallback;
- enable Airtable when the learner needs cross-course analytics, while keeping `github_to_airtable` and no mastery authority.

Any task-backend change must migrate or reconcile the authoritative execution state and leave only one authoritative backend. Preserve safe identifiers in `state/integrations.json`, archive or mark superseded resources, and never infer mastery from the old or new external provider.

External integration changes do not silently rewrite approved objectives, mastery criteria or assessment evidence. Apply the same draft PR, internal review, CI and safe-merge policy used for curriculum changes when repository contracts change.

## Independent replan review

After preparing the change, run `instructions/04-review-generated-artifacts.md` with the `replan` profile.

The replan reviewer must verify that:

- a learner request, changed constraint, diagnostic evidence or mastery result actually triggered the change;
- completed evidence and history remain intact;
- unchanged goals and preferences were preserved;
- new, removed or split topics keep a valid dependency graph and responsible effort;
- affected content versions, assessments and specialized content reviews are refreshed;
- integration changes are justified and preserve exactly one authoritative task backend;
- learner-visible impact and the next action are accurate.

A curriculum or provider change that cannot be justified from persisted evidence is blocking. Do not rewrite earlier history to make the new plan appear original.

Store the approval under `state/reviews/<replan-operation>.yml` with current fingerprints and reviewed deletion evidence for every affected generated artifact.

## Migration boundary

When replan requires moving state between repositories, providers or incompatible template contracts, execute the migration as a distinct operation with the `migration` profile instead of hiding it inside the replan approval.

The migration reviewer must verify exact source and target identities, compatibility, state preservation, idempotent reruns, duplicate prevention, rollback safety and reviewed deletions. Replan may continue only after the migration review is approved.

Complete the phase using `instructions/phase-completion.md` after specialized review, shared replan or migration review, generated diff coverage and CI succeed. Summarize only what materially changed and why, link the updated roadmap, integration plan or pull request, and provide one exact command for returning to progress tracking or reviewing a changed topic.
