# Template and instance lifecycle

Open Study Path separates the reusable engine from each learner's generated content and external integrations.

```mermaid
flowchart TD
    T[Canonical template repository] --> F[Fork or create from template]
    F --> S[Add ANTHROPIC_API_KEY as a repository Secret]
    S --> B[Dispatch bootstrap_instance via Agent pilot]
    B --> IM[Record repository in instance marker]
    IM --> P{Select intake provider}
    P -->|GitHub Issue Form| GI[Use form already copied with fork]
    P -->|Jotform| JA[Currently unreachable: no dispatched phase wires it]
    P -->|Manual YAML| MY[Edit study.config.yml]
    GI --> R[Intake method ready]
    MY --> R
    R --> I[Import explicitly approved intake]
    I --> D[Run diagnostic]
    D --> G[Generate curriculum proposal]
    G --> PR[Review and merge pull request]
    PR --> X[Publish tasks and track evidence]
```

## Template mode

Template mode contains reusable contracts only. The canonical repository has `.open-study-path/template.yml` and no `.open-study-path/instance.yml`.

Allowed changes:

- improve instructions and schemas;
- improve intake specifications;
- improve generated-file templates;
- improve agent-pilot onboarding documentation;
- test validation and documentation.

Forbidden changes:

- learner-specific configuration;
- learner-owned Jotforms or integration identifiers;
- imported submissions;
- generated roadmaps or topics;
- learner task boards and calendar events;
- progress or achievement state.

## Agent-pilot setup

Every phase runs as an isolated Claude API call dispatched through GitHub Actions -- see `docs/claude-agent-pilot.md` for the design and `docs/claude-agent-setup.md` for the setup steps. Add `ANTHROPIC_API_KEY` as a repository Secret on the instance repository, then dispatch `bootstrap_instance` (and, when needed, `configure_intake`) from the **Agent pilot** workflow with `target_repo` set to that same repository.

There is no separate copied-instructions file to keep in sync: the workflow reads `AGENTS.md` and `instructions/*.md` directly at run time. During bootstrap, the agent records the exact repository identity in `.open-study-path/instance.yml`; that marker becomes the persistent repository source of truth once it exists.

A mismatch between the marker and the repository the workflow is actually running in must stop repository writes until the owner resolves it.

## Fork setup

A fork is not automatically an instance. The owner explicitly asks an agent to set it up.

Setup has two internal phases:

1. bootstrap the empty instance files and persist the repository identity;
2. configure one intake provider.

Setup stops when the intake method is ready. It does not import a response or generate a curriculum.

## Intake providers

### GitHub Issue Form

The form under `.github/ISSUE_TEMPLATE/create-study-path.yml` is copied into every fork. It requires no external authorization and is the recommended zero-configuration option.

### Jotform

The owner authorizes the connected Jotform account. The agent creates an instance-owned form from `intake/jotform-form-spec.yml`, persists only its ID, URL and specification version, and then stops. No maintainer form is shared across instances.

Currently unreachable: only the `github_issue` provider is wired to a dispatched `configure_intake`/`intake` phase (`docs/claude-agent-pilot.md`). This section describes the contract Jotform intake must follow whenever it gets its own dispatched path.

### Manual YAML

The owner may enter the required facts directly in `study.config.yml`. Placeholder defaults are not treated as confirmed learner answers.

## Instance mode

Instance mode begins when `.open-study-path/instance.yml` is created in a repository other than the canonical template. The instance may then configure intake, import an approved response, generate its learning path and connect optional task or calendar backends.

## Updating from the template

Instance repositories should keep learner-generated files separate from reusable template files so upstream template changes can be compared and merged without replacing progress, integration identifiers or study content.