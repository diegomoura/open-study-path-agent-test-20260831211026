#!/usr/bin/env python3
"""Validate the executable projection contract, journals and durable state."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from task_projection_engine import (
    SUPPORTED_PROVIDERS,
    VISIBLE_STATES,
    VisibleFields,
    validate_visible_fields,
)

ROOT = Path(__file__).resolve().parents[1]
OPERATION_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
TOPIC_ID = re.compile(r"^TOPIC-[0-9]{3,}$")
SUCCESS = {"success", "completed", "succeeded"}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {display_path(path)}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in {display_path(path)}: {exc.msg} at line {exc.lineno}"
        ) from exc


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def text(value: Any) -> str:
    return str(value or "").strip()


def validate_contract(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = (
        root / "instructions/41-task-backend-projection.md",
        root / "scripts/task_projection_engine.py",
        root / "scripts/operation_branch.py",
        root / "scripts/render_integration_summary.py",
        root / "schemas/publication-operation.schema.json",
        root / "schemas/integrations-state.schema.json",
        root / "templates/integrations-state.json",
        root / "docs/task-projection-architecture.md",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"missing projection artifact: {display_path(path)}")

    contract = required[0]
    if contract.is_file():
        body = contract.read_text(encoding="utf-8")
        fragments = (
            " → ".join(VISIBLE_STATES),
            "exactly one",
            "state/operations/<operation-id>.json",
            "one issue per materialized lesson",
            "study:ready",
            "read-back",
            "Historical reviews remain immutable",
            "one convergent branch",
        )
        for fragment in fragments:
            if fragment not in body:
                errors.append(f"projection contract is missing: {fragment}")

    template = root / "templates/integrations-state.json"
    if template.is_file():
        try:
            data = load_json(template)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if data.get("version") != 3:
                errors.append("integration state template must use version 3")
            if "operations" not in data or "projection" not in data:
                errors.append("integration state template requires operations and projection")
    return errors


def validate_operation(path: Path) -> list[str]:
    label = display_path(path)
    try:
        data = load_json(path)
    except ValueError as exc:
        return [str(exc)]
    if not isinstance(data, dict):
        return [f"{label} must contain one JSON object"]

    errors: list[str] = []
    if not isinstance(data.get("operation_id"), str) or not OPERATION_ID.fullmatch(
        data["operation_id"]
    ):
        errors.append(f"{label} has invalid operation_id")
    if data.get("provider") not in SUPPORTED_PROVIDERS:
        errors.append(f"{label} has unsupported provider {data.get('provider')!r}")
    if data.get("operation_type") not in {
        "publication",
        "assessment_projection",
        "reconciliation",
        "migration",
    }:
        errors.append(f"{label} has invalid operation_type")
    # Etapa 6d real finding: `mode` and `topics` were never fields on the
    # real task_projection_engine.OperationJournal dataclass -- this
    # validator's schema for them predates (or was never reconciled with)
    # what the real engine actually writes. A real evaluate dispatch
    # persisted the real, unmodified journal returned by
    # run_publish_projection and was rejected for missing both. This
    # validator's own existing tests never caught the mismatch either,
    # since their fixture was hand-built to include both fields rather
    # than sourced from a real OperationJournal.as_dict()/asdict() call.
    if data.get("status") not in {
        "not_started",
        "in_progress",
        "partial",
        "blocked",
        "failed",
        "success",
    }:
        errors.append(f"{label} has invalid status")
    for name in ("attempt", "external_read_count", "external_write_count", "commit_budget"):
        value = data.get(name)
        minimum = 1 if name in {"attempt", "commit_budget"} else 0
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            errors.append(f"{label} has invalid {name}")
    if not isinstance(data.get("checkpoints"), list):
        errors.append(f"{label} checkpoints must be a list")
    if data.get("status") == "success":
        if not data.get("completed_at"):
            errors.append(f"{label} success operation requires completed_at")
        if data.get("external_read_count", 0) < 1:
            errors.append(f"{label} success operation requires final read-back")
    return errors


def _visible_payload_errors(resource: Mapping[str, Any], label: str) -> list[str]:
    visible = mapping(resource.get("visible"))
    fields = VisibleFields(
        title=text(visible.get("title")),
        description=text(visible.get("description")),
        checklist=tuple(value for value in visible.get("checklist", []) if isinstance(value, str)),
        managed_comments=tuple(
            value for value in visible.get("managed_comments", []) if isinstance(value, str)
        ),
    )
    return [f"{label}: {error}" for error in validate_visible_fields(fields)]


def validate_projection_state(root: Path = ROOT) -> list[str]:
    marker = root / ".open-study-path/instance.yml"
    state_path = root / "state/integrations.json"
    if not marker.is_file() or not state_path.is_file():
        return []
    try:
        data = load_json(state_path)
    except ValueError as exc:
        return [str(exc)]
    if not isinstance(data, dict):
        return ["state/integrations.json must contain one JSON object"]

    sync = mapping(data.get("sync"))
    resolution = mapping(data.get("resolution"))
    if text(sync.get("status")).lower() not in SUCCESS:
        return []

    errors: list[str] = []
    if data.get("version") != 3:
        errors.append("successful integration state must use version 3")
    if resolution.get("status") != "resolved":
        errors.append("successful integration state requires resolution.status resolved")
    projection = mapping(data.get("projection"))
    if not projection:
        return errors + ["successful integration state requires projection"]
    provider = text(projection.get("provider"))
    if provider not in SUPPORTED_PROVIDERS:
        errors.append(f"projection has unsupported provider: {provider!r}")
    resources = [item for item in data.get("resources", []) if isinstance(item, Mapping)]
    lessons = [item for item in resources if item.get("topic_id")]
    topic_count = projection.get("topic_count")
    if topic_count != len(lessons):
        errors.append("projection topic_count does not match lesson resources")
    topic_ids = [item.get("topic_id") for item in lessons]
    if len(topic_ids) != len(set(topic_ids)):
        errors.append("projection contains duplicate topic_id resources")
    if any(not isinstance(value, str) or not TOPIC_ID.fullmatch(value) for value in topic_ids):
        errors.append("projection contains an invalid topic_id")

    readback = mapping(projection.get("readback"))
    if not readback.get("verified_at"):
        errors.append("successful projection requires readback.verified_at")
    if readback.get("lesson_card_count") != len(lessons):
        errors.append("readback lesson count does not match resources")
    if readback.get("visible_internal_marker_count") != 0:
        errors.append("readback found learner-visible internal metadata")

    primary = [item for item in lessons if item.get("visible_state") == "Próxima aula"]
    eligible = [
        item
        for item in lessons
        if item.get("visible_state") in {"Próxima aula", "Disponível em paralelo"}
    ]
    if eligible and len(primary) != 1:
        errors.append("eligible unfinished lessons require exactly one Próxima aula")

    if provider in {"trello", "todoist"}:
        if projection.get("managed_list_order") != list(VISIBLE_STATES):
            errors.append("ordered projection has incorrect managed list order")
        orientation = [item for item in resources if item.get("type") == "orientation"]
        if len(orientation) != 1:
            errors.append("projection requires exactly one orientation resource")
        expected_managed = len(lessons) + 1
        if readback.get("managed_card_count") != expected_managed:
            errors.append("managed readback count must include lessons and orientation only")

    for index, resource in enumerate(resources):
        if "visible" in resource:
            errors.extend(_visible_payload_errors(resource, f"resource #{index + 1}"))
    if not sync.get("last_success_at"):
        errors.append("successful projection requires sync.last_success_at")
    return errors


def main() -> int:
    errors = validate_contract()
    errors.extend(validate_projection_state())
    operations = ROOT / "state/operations"
    if operations.is_dir():
        for path in sorted(operations.glob("*.json")):
            errors.extend(validate_operation(path))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Task projection engine, journals and durable state are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
