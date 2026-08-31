# Capability-based integration preflight

Run this preflight inside the `publish` phase before any external write.

## Inputs

Read:

- `study.config.yml`;
- approved `study/integrations.md`;
- `state/integrations.json`;
- exact repository identity from `.open-study-path/instance.yml`.

Do not infer enabled providers from a global app catalog. A provider is relevant only when selected for an immediate current action.

## Account-connection policy

Read `integration_preferences.account_connections` before app discovery, probes or writes.

When it is `no_external_accounts`:

- do not suggest, install, connect, probe or write to a provider that requires another account;
- do not treat `already_uses` as permission to connect that provider;
- resolve task tracking to GitHub Issues or repository Markdown;
- use Mermaid, repository artifacts, primary sources, web research and chat;
- keep reminders, calendars and email inactive.

When it is `ask_per_provider`, every optional connection remains contextual, nonblocking and subject to an explicit user click. Respect restrictions recorded in `integration_preferences.notes`.

## Classify capabilities

Classify every capability as one of:

- `required_for_selected_publication` — its provider must be available before the required publication set begins;
- `optional_current_action` — activate only because the learner needs it now and supplied the required details;
- `not_enabled` — no probe, write, connection suggestion or learner-facing status line.

GitHub access is always required. The authoritative external task backend is required when selected. Research, reminders, scheduling, habits, external visuals, artifact workspaces, analytics, course discovery and email are optional.

Flashcard and Quizlet capabilities are not part of Open Study Path. Do not discover, suggest, probe or create them.

## Provider resolution

Resolve only the concrete providers needed now:

- task manager: Trello, Todoist, GitHub Issues or Markdown;
- flexible reminders: Todoist or none;
- fixed scheduling: Google Calendar, Outlook Calendar or none;
- research: Consensus, web or none;
- habits: Habitify or none;
- external visuals: Whimsical, Miro, Lucid, Figma or none;
- artifacts: Google Drive, Notion, SharePoint, Dropbox or none;
- analytics: Airtable or none;
- email action: Gmail, Outlook email or none.

A value of `auto` must already have a documented current reason and fallback in `study/integrations.md`. Resolve it before writes and persist the actual provider used when state changes.

## Routine resolution

Read `integration_preferences.routine` before probing Todoist or a calendar.

- `fixed_calendar` selects one calendar provider and disables flexible Todoist reminders for the same routine.
- `flexible_reminders` selects Todoist reminders and disables calendar events for the same routine.
- `none` and `decide_later` activate neither capability.
- `custom` requires interpreting `routine.details`; ask one concise question when the minimum data cannot be resolved.

For fixed calendar blocks, require days or dates, start time, duration, timezone and selected calendar. For flexible reminders, require recurrence or trigger and any requested reminder time. Do not create empty placeholder events or reminders.

## Optional app discovery and connection offer

For an optional provider marked `selected` for an immediate current action, confirm that the action can be completed after connection. Then:

1. use Plugin Management to search for the exact provider;
2. render one install or connect suggestion when available;
3. never install, connect or authorize silently;
4. do not ask a separate text-only confirmation before the control;
5. show at most one suggestion for the same provider and at most three in one response;
6. continue independent repository work without waiting when the provider is optional;
7. never claim connection merely because the suggestion was shown.

Do not suggest providers that are declined, forbidden, inactive, irrelevant or already verified.

## Verify actual access

A provider name, installed app, visible tool definition, connection suggestion or learner statement does not prove authorization.

For every provider required for the current action, execute one harmless minimal read supported by its connector. Examples:

- GitHub: read the instance marker or repository metadata;
- Trello: list a small number of boards;
- Todoist: list a small number of projects or tasks;
- Google or Outlook Calendar: list calendars or a bounded event window;
- Gmail or Outlook email: list labels or folders only when an email action was explicitly requested;
- other optional providers: list a small number of accessible resources when their current action requires it.

Use only exposed operations. Never request API keys, tokens or passwords. Never create a disposable resource to test access.

## Gmail is available on request, not preconfigured

Do not probe Gmail during normal task publication. Do not persist `status: configured` or an automatic delivery policy merely because the connector is available.

When the learner explicitly asks to send or draft a summary:

1. verify Gmail access at that moment;
2. resolve recipient, scope and send-versus-draft when genuinely missing;
3. perform only the requested action;
4. persist no automatic schedule unless the learner separately requests a recurring automation.

Until an email action is requested, `notifications.provider` remains `chat` and `email_enabled` remains `false`.

## Required-provider atomicity

Complete every required probe before creating any required external resource.

When one or more required providers are unavailable:

1. create no resource in the required publication set;
2. do not partially publish through other required providers;
3. name only the unavailable required providers;
4. tell the owner to connect or authorize those apps, then re-run this phase.

There is no persistent chat session to resume in the automated-only flow: the owner fixes the missing connection or configuration and simply dispatches `publish` again. Re-running does not by itself prove access -- run the read-only probes again on the next dispatch.

## Optional-provider fallback

When an optional current-action provider is unavailable:

1. create no resource in that provider;
2. use the approved repository-native or chat alternative;
3. record a short non-sensitive reason only when state changes are already in scope;
4. continue the required publication operation;
5. mention the fallback only when it changes what the learner should do next.

Optional failure must never block study, assessment, review or mastery.

## Idempotency before writes

Before creating resources, inspect exact records in `state/integrations.json` and search the provider for matching resources when supported. Reuse or update valid resources rather than creating duplicates.

Match on capability, provider, external type, topic ID, content version and stable course identifier. An interrupted publication must record what was actually created or updated.

## Continue after probes

When required probes pass, do not send an intermediate “connections verified” response. Continue directly with publication and the final learner-facing response.

## Blocked response

Use a brief response equivalent to:

> Resultado: publicação pausada antes de qualquer criação externa obrigatória.
>
> Atenção: não foi possível verificar a conexão com `<providers>`.
>
> Depois de resolver a conexão, despache a fase `publish` novamente.

Do not list inactive optional providers in the blocked response.
