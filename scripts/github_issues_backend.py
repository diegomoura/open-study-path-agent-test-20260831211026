#!/usr/bin/env python3
"""A real `github_issues` adapter for scripts/task_projection_engine.py's Backend protocol.

scripts/task_projection_engine.py already contains the entire provider-
independent projection algorithm (matching, idempotency, read-back
validation, visible-content boundary checks) plus a `FakeBackend` used by its
own tests. This module is the missing piece for a real dispatch: an adapter
that implements the same `Backend` protocol against the real GitHub REST API,
so `publish_projection()` can run unmodified against a live repository.

Etapa 4 (proposal, section 7, step 4) scopes `publish` to `github_issues`
only -- Trello/Todoist need their own Secret and their own adapter, deferred
per docs/claude-agent-pilot.md's Scope section.

Design notes, since they matter for anyone reviewing or extending this:

- Matching tiers. instructions/41-task-backend-projection.md orders matching
  as (1) durable external ID, (2) private stable key, (3) exactly one
  compatible visible-title match. Tier 2 has no real GitHub equivalent
  without writing a hidden marker into the issue body -- which
  instructions/41's "Visible-content boundary" section explicitly forbids.
  This adapter only implements tiers 1 and 3. Idempotency across reruns
  still works: the harness passes each topic's previously-known
  `external_id` (read from state/integrations.json) back in on every call,
  so tier 1 resolves it directly without ever touching tier 2.
- The "container" GitHub Issues has no board/project resource. `ensure_
  container` returns the repository itself (id = "owner/repo", url =
  the repository's URL) without any real write -- the repository already
  exists by construction, since this backend only ever runs inside the
  workflow's own repository (GITHUB_REPOSITORY), same boundary already
  established for the `intake` phase's GitHub Issues tools.
- No managed sections/lists. `ORDERED_PROVIDERS` in task_projection_engine.py
  is `{"trello", "todoist"}` -- github_issues has no list/column concept, so
  `ensure_managed_sections` is a no-op, matching how `FakeBackend` already
  treats non-ordered providers.
- Labels. `visible_state` maps to exactly one `study:*` label via the
  engine's own `GITHUB_STATE_LABELS`. Any existing non-`study:` labels on an
  issue are preserved; any existing `study:` label is replaced (an issue
  should only ever carry the one label matching its current visible state).
- Internal metadata (topic_id, direct prerequisite IDs, content version,
  roadmap fingerprint, resource URLs) can never live in the issue's visible
  title/body/labels -- instructions/41's "Visible-content boundary" forbids
  exactly that. But the engine already hands this adapter fresh, correct
  `internal_metadata` as a parameter on every `upsert_managed_resource` call
  (recomputed from the current approved roadmap by `build_projection_plan`),
  so the adapter only needs to remember it in memory for the lifetime of one
  `publish_projection()` call, then echo it back in `read_normalized_
  snapshot()`. No metadata needs to round-trip through GitHub at all --
  `state/integrations.json` is the durable store across separate runs
  (matches "Store synchronization metadata only in state/integrations.json,
  the operation journal, or a genuinely private provider field").
- All issues in the repository are listed once (open and closed, paginated)
  and cached for the lifetime of one backend instance, then matched
  client-side by title. This is simpler and more reliable for a roadmap-
  sized issue count than GitHub's fuzzy search API, and it means a single
  backend instance makes exactly one list call regardless of roadmap size.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from task_projection_engine import GITHUB_STATE_LABELS, VisibleFields

RequestJson = Any  # scripts.agent_runtime.RequestJson at runtime; kept loose to avoid an import cycle


@dataclass
class GitHubIssuesBackend:
    """Real `Backend` implementation for provider="github_issues"."""

    request_json: RequestJson
    repository: str
    provider: str = "github_issues"
    _write_log: list[dict[str, Any]] = field(default_factory=list, init=False)
    _issues_by_number: dict[int, dict[str, Any]] = field(default_factory=dict, init=False)
    _metadata_by_number: dict[int, Mapping[str, Any]] = field(default_factory=dict, init=False)
    _issues_loaded: bool = field(default=False, init=False)

    # -- Backend protocol -------------------------------------------------

    @property
    def write_count(self) -> int:
        return len(self._write_log)

    @property
    def write_log(self) -> Sequence[Mapping[str, Any]]:
        return tuple(dict(entry) for entry in self._write_log)

    def preflight_match(
        self,
        *,
        resource_kind: str,
        durable_external_id: str | None,
        stable_key: str,
        visible_title: str,
    ) -> str | None:
        del resource_kind, stable_key  # not used by this adapter; see module docstring
        self._ensure_issues_loaded()
        if durable_external_id:
            number = int(durable_external_id)
            if number in self._issues_by_number:
                return str(number)
            # A stale external_id (issue deleted/transferred) is not treated
            # as ambiguous -- fall through to a title match instead of
            # raising, since the caller can still recover by creating a new
            # issue and recording its number.
        title_matches = [
            issue for issue in self._issues_by_number.values() if issue["title"] == visible_title
        ]
        if len(title_matches) == 1:
            return str(title_matches[0]["number"])
        if len(title_matches) > 1:
            from task_projection_engine import AmbiguousMatchError

            raise AmbiguousMatchError(
                f"{len(title_matches)} open/closed issues share the title {visible_title!r} "
                f"in {self.repository}"
            )
        return None

    def ensure_container(self, name: str) -> Mapping[str, Any]:
        del name  # no real GitHub resource to name; see module docstring
        return {"id": self.repository, "url": f"https://github.com/{self.repository}"}

    def ensure_managed_sections(self, names: Sequence[str]) -> None:
        del names  # github_issues is not in ORDERED_PROVIDERS; no-op by design

    def upsert_managed_resource(
        self,
        *,
        resource_kind: str,
        stable_key: str,
        durable_external_id: str | None,
        visible: VisibleFields,
        internal_metadata: Mapping[str, Any],
        visible_state: str,
    ) -> Mapping[str, Any]:
        del stable_key
        self._ensure_issues_loaded()
        body = _render_body(visible)
        desired_label = GITHUB_STATE_LABELS.get(visible_state) if resource_kind == "lesson" else None

        number_str = self.preflight_match(
            resource_kind=resource_kind,
            durable_external_id=durable_external_id,
            stable_key="",
            visible_title=visible.title,
        )

        if number_str is None:
            labels = [desired_label] if desired_label else []
            created = self.request_json(
                "POST",
                f"/repos/{self.repository}/issues",
                {"title": visible.title, "body": body, "labels": labels},
            )
            self._write_log.append({"action": "create_resource", "kind": resource_kind, "number": created["number"]})
            self._remember(created)
            self._metadata_by_number[created["number"]] = internal_metadata
            return self._normalize(self._issues_by_number[created["number"]], created["number"])

        number = int(number_str)
        existing = self._issues_by_number[number]
        self._metadata_by_number[number] = internal_metadata
        changes: dict[str, Any] = {}
        if existing["title"] != visible.title:
            changes["title"] = visible.title
        if existing["body"] != body:
            changes["body"] = body
        if desired_label is not None:
            kept = [label for label in existing["labels"] if not label.startswith("study:")]
            desired_labels = sorted(set(kept + [desired_label]))
            if sorted(existing["labels"]) != desired_labels:
                changes["labels"] = desired_labels
        if changes:
            updated = self.request_json("PATCH", f"/repos/{self.repository}/issues/{number}", changes)
            self._write_log.append({"action": "update_resource", "kind": resource_kind, "number": number, "fields": sorted(changes)})
            self._remember(updated)
            return self._normalize(self._issues_by_number[number], number)

        return self._normalize(existing, number)

    def read_normalized_snapshot(self) -> Mapping[str, Any]:
        # Re-list rather than trust the local cache: this is the read-back
        # instructions/41-task-backend-projection.md requires ("read the
        # complete board, project or issue set") before publication success
        # is reported, and it must reflect exactly what the API has now, not
        # what this process assumed it wrote. `_metadata_by_number` is
        # untouched by this re-list -- it survives because it was populated
        # by upsert_managed_resource earlier in this same backend instance's
        # lifetime, not derived from the GitHub response.
        self._issues_loaded = False
        self._ensure_issues_loaded()
        resources = [
            self._normalize(issue, number)
            for number, issue in self._issues_by_number.items()
            if _is_managed(issue)
        ]
        return {
            "provider": self.provider,
            "container": {"id": self.repository, "url": f"https://github.com/{self.repository}"},
            "sections": [],
            "resources": resources,
        }

    # -- internal -----------------------------------------------------------

    def _ensure_issues_loaded(self) -> None:
        if self._issues_loaded:
            return
        self._issues_by_number = {}
        page = 1
        while True:
            batch = self.request_json(
                "GET",
                f"/repos/{self.repository}/issues?state=all&per_page=100&page={page}",
                None,
            )
            if not batch:
                break
            for item in batch:
                if "pull_request" in item:
                    continue
                self._remember(item)
            if len(batch) < 100:
                break
            page += 1
        self._issues_loaded = True

    def _remember(self, raw_issue: Mapping[str, Any]) -> None:
        self._issues_by_number[raw_issue["number"]] = {
            "number": raw_issue["number"],
            "title": raw_issue.get("title", ""),
            "body": raw_issue.get("body") or "",
            "labels": [label.get("name", "") if isinstance(label, Mapping) else label for label in raw_issue.get("labels", [])],
            "url": raw_issue.get("html_url", f"https://github.com/{self.repository}/issues/{raw_issue['number']}"),
        }

    def _normalize(self, issue: Mapping[str, Any], number: int) -> dict[str, Any]:
        # `issue` is always an already-cached, normalized dict (see
        # `_remember`) -- this only reshapes it into the Backend protocol's
        # resource shape (VisibleFields-like dict, visible_state, kind), and
        # attaches whatever internal_metadata this run's upsert calls
        # recorded for this issue number (empty for an issue this run never
        # touched -- see the module docstring's note on stale issues).
        labels = list(issue["labels"])
        kind = "lesson" if any(label.startswith("study:") for label in labels) else "orientation"
        # GITHUB_STATE_LABELS is many-to-one: "Disponível em paralelo" and
        # "Próxima aula" both render as the same study:ready label, since
        # GitHub Issues has no third state to distinguish them visually. A
        # naive dict inversion ({value: key for key, value in ...}) always
        # resolves that collision to whichever visible_state was inserted
        # last in GITHUB_STATE_LABELS ("Próxima aula"), so *every*
        # study:ready issue read back this way -- including ones this run
        # itself just wrote as "Disponível em paralelo" -- was silently
        # reported as "Próxima aula" instead. That was invisible until a
        # real dispatch had two eligible topics at once for the first time
        # in this harness's history, and validate_readback's primary/
        # parallel checks (which need to tell them apart) failed outright.
        # Prefer this run's own internal_metadata (populated by
        # upsert_managed_resource earlier in this same backend instance's
        # lifetime, so it reflects exactly what THIS run intended for an
        # issue it just wrote) when present; only fall back to the lossy
        # label-based guess for an issue this run never touched, where no
        # better source of truth exists.
        metadata = dict(self._metadata_by_number.get(number, {}))
        metadata_visible_state = metadata.get("visible_state")
        if isinstance(metadata_visible_state, str) and metadata_visible_state in GITHUB_STATE_LABELS:
            visible_state = metadata_visible_state
        else:
            state_by_label = {value: key for key, value in GITHUB_STATE_LABELS.items()}
            visible_state = next(
                (state_by_label[label] for label in labels if label in state_by_label),
                "Planejado",
            )
        return {
            "id": str(number),
            "url": issue["url"],
            "kind": kind,
            "managed": True,
            "visible": {"title": issue["title"], "description": issue["body"], "checklist": [], "managed_comments": []},
            "internal_metadata": metadata,
            "visible_state": visible_state,
            "labels": labels,
        }


def _is_managed(issue: Mapping[str, Any]) -> bool:
    # Every issue this adapter creates or updates carries a study:* label
    # (lessons) or is the single pinned orientation issue. An issue with
    # neither is learner- or maintainer-created and out of scope -- it must
    # never be swept into the projection snapshot, matching instructions/41's
    # instruction to "preserve learner-owned resources".
    if any(str(label).startswith("study:") for label in issue.get("labels", [])):
        return True
    return issue.get("title") == "📌 Leia antes de começar"


def _render_body(visible: VisibleFields) -> str:
    body = visible.description
    if visible.checklist:
        checklist_block = "\n".join(f"- [ ] {item}" for item in visible.checklist)
        body = f"{body}\n\n## Sua sessão de estudo\n\n{checklist_block}"
    return body
