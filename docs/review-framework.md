# Open Study Path Review Framework

The review framework makes independent review part of every artifact-producing operation. It complements deterministic validation: CI can prove that required files, fingerprints and decisions are present, while a reviewer must still judge meaning, pedagogy, safety and consistency.

## Core rule

Every generated artifact changed by an instance operation must be covered by an approved review artifact changed in the same pull request.

The review happens after authoring and before merge:

```text
approved inputs
      ↓
authoring pass
      ↓
independent review pass
      ↓
correction of blocking findings
      ↓
deterministic validation
      ↓
safe merge
```

The reviewer does not accept the author's statement that the operation succeeded. The reviewer reconstructs the result from repository artifacts, external read-backs when available and the approved state that preceded the operation.

## Review profiles

| Profile | Reviewer role | Main responsibility |
| --- | --- | --- |
| `setup` | `setup_reviewer` | Repository identity, inherited assets, intake readiness and safe configuration |
| `intake` | `intake_reviewer` | Preserve the learner's request and preferences without unsupported inference |
| `diagnostic` | `diagnostic_reviewer` | Ground placement in bounded evidence and keep adjacent experience separate from subject mastery |
| `curriculum` | `curriculum_reviewer` | Check scope, dependency graph, effort, content-review completion, assessments, sources and integration plan |
| `publication` | `publication_reviewer` | Check selected tools, external projections, idempotency, authority, privacy, cost and next action |
| `assessment` | `assessment_reviewer` | Check submission resolution, rubric-based scoring, feedback, progress and subsequent materialization |
| `progress` | `progress_reviewer` | Check valid state transitions, projections and next-action routing |
| `replan` | `replan_reviewer` | Check evidence for change, scope preservation, graph validity, versions and learner impact |
| `migration` | `migration_reviewer` | Check source/target identity, compatibility, state preservation, idempotency and rollback safety |

The specialized course-content reviewer in `instructions/36-review-course-content.md` remains mandatory for materialized teaching content. The curriculum profile verifies that those reviews exist and that the course works as a coherent whole.

## Durable review artifact

Store the review under `state/reviews/` using `templates/review.yml`.

A review records:

- the operation and profile;
- the specialized reviewer role;
- confirmation that review was a separate pass;
- exact SHA-256 fingerprints of current generated artifacts;
- the previous base fingerprint for each reviewed deletion;
- required checks and their disposition;
- blocking and non-blocking findings;
- review time and status.

A review is mergeable only when:

- `status` is `approved`;
- `independent_pass` is `true`;
- every required profile check is `passed`;
- `blocking_findings` is empty;
- every current covered artifact exists and its SHA-256 matches the review;
- every reviewed deletion is absent at the head and its `previous_sha256` matches the file in the pull-request base;
- every generated artifact changed in the pull request is covered by at least one approved review artifact changed in that pull request.

A changed output invalidates its previous fingerprint. The operation must run a new review pass rather than reusing an old approval.

## What CI can and cannot prove

CI blocks:

- generated changes without review;
- incomplete profile checklists;
- stale fingerprints;
- deletion claims that do not match the pull-request base;
- unknown reviewer roles or profiles;
- approval with blocking findings;
- a review that covers only part of the generated diff;
- malformed review artifacts.

CI cannot determine by keyword matching that an explanation is pedagogically correct, a score is fair or a source truly supports a nuanced claim. The reviewer remains responsible for semantic honesty and must actively search for contradictions.

## Findings

Use `blocking` when the current result is unsafe, inconsistent, incomplete or materially different from the approved operation. Examples:

- learner preference disappears;
- placement has no evidence;
- roadmap promise is not delivered;
- assessment asks for untaught content;
- external publication reports success without resolution;
- score does not follow the rubric;
- progress or next action is wrong;
- migration loses or duplicates state;
- privacy, cost or destructive-write risk is unresolved.

Use `non_blocking` for improvements that do not invalidate the current result.

Correct resolvable blocking findings on the operation branch. Ask the owner only when a real pedagogical, scope, privacy, cost or destructive decision remains.

## Pull-request coverage gate

The inherited workflow checks the diff against the pull request base. Generated instance paths include:

- `.open-study-path/instance.yml`;
- `study.config.yml`;
- generated files under `study/`;
- generated state under `state/`;
- intake and assessment Issue Forms.

Generic reviews under `state/reviews/` and specialized content reviews under `state/content-reviews/` are review evidence, so they are not required to review themselves.

A current or added artifact uses `change: current` and `sha256`. A reviewed deletion uses `change: deleted` and `previous_sha256`; CI reads the exact base file before accepting the deletion. This allows safe cleanup and migration without making deletion an unreviewed exception.

Reusable template files such as scripts, instructions and templates are governed by normal template development review rather than learner-instance review artifacts.

## Compatibility

New instances enable the framework by default. Legacy instances without `review_framework.enabled: true` remain compatible until explicitly migrated. Once enabled, generated artifact changes cannot merge without current review coverage.
