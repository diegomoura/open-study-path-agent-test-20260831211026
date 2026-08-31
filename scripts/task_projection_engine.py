#!/usr/bin/env python3
"""Provider-independent, resumable task projection engine.

The module contains no connector-specific dependencies. Production adapters can
implement the small backend protocol while tests use :class:`FakeBackend`.
Visible learner copy and internal synchronization metadata are deliberately
separate data structures.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Protocol, Sequence

INTERNAL_STATES = (
    "planned",
    "ready",
    "in_progress",
    "in_assessment",
    "review_required",
    "completed",
)
VISIBLE_STATES = (
    "Planejado",
    "Disponível em paralelo",
    "Próxima aula",
    "Em estudo",
    "Em avaliação",
    "Revisão necessária",
    "Concluído",
)
ORDERED_PROVIDERS = {"trello", "todoist"}
SUPPORTED_PROVIDERS = {"trello", "todoist", "github_issues"}
LEGACY_SECTION_ALIASES = {
    "Pronto para estudar": "Próxima aula",
    "Em andamento": "Em estudo",
}
LEGACY_GITHUB_LABELS = {
    "study:ready-primary": "study:ready",
    "study:ready-parallel": "study:ready",
}
GITHUB_STATE_LABELS = {
    "Planejado": "study:planned",
    "Disponível em paralelo": "study:ready",
    "Próxima aula": "study:ready",
    "Em estudo": "study:in-progress",
    "Em avaliação": "study:in-assessment",
    "Revisão necessária": "study:review-required",
    "Concluído": "study:completed",
}

KNOWN_HTML_MARKER = re.compile(
    r"<!--\s*open-study-path\b.*?-->", re.IGNORECASE | re.DOTALL
)
VISIBLE_METADATA_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("HTML comment", re.compile(r"<!--", re.IGNORECASE)),
    (
        "open-study-path marker",
        # Etapa 6a/6c real finding: the bare \bopen-study-path\b word-boundary
        # match also fires on any repository whose *name* merely contains
        # this product-name substring (e.g. this pilot's own disposable test
        # repos, "open-study-path-agent-test-..."), which is never a leak --
        # it's just the repo's URL. The real marker syntax used everywhere
        # (issue-template HTML comments, hidden metadata) always has a colon
        # immediately after "open-study-path" (open-study-path:topic_id=...,
        # open-study-path:assessment topic_id=...); a bare repository name
        # never does, since repo names use hyphens, not colons. Requiring
        # the colon keeps this pattern catching every real leak (a marker
        # that lost its HTML-comment wrapper but kept its own syntax) while
        # no longer flagging a legitimate, already-public repository URL.
        re.compile(r"\bopen-study-path:", re.IGNORECASE),
    ),
    ("internal topic id", re.compile(r"\bTOPIC-\d{3,}\b")),
    ("content_version", re.compile(r"\bcontent_version\b", re.IGNORECASE)),
    (
        "serialized prerequisite array",
        re.compile(r"\[\s*[\"']?TOPIC-\d{3,}", re.IGNORECASE),
    ),
    (
        "fingerprint",
        re.compile(r"\b(?:roadmap_)?fingerprint\b|\bsha256\s*[:=]", re.IGNORECASE),
    ),
    (
        "provider id",
        re.compile(
            r"\b(?:provider|board|project|card|task|issue|list)_id\b",
            re.IGNORECASE,
        ),
    ),
    (
        "synchronization payload",
        re.compile(
            r"[\{,]\s*[\"'](?:operation_id|sync|external_id|managed_fields_version)[\"']\s*:",
            re.IGNORECASE,
        ),
    ),
)


class ProjectionError(RuntimeError):
    """Base error for projection failures."""


class AmbiguousMatchError(ProjectionError):
    """Raised before writes when an existing resource cannot be resolved safely."""


class PartialWriteError(ProjectionError):
    """Raised by a backend after an injected or real partial failure."""


class ReadbackValidationError(ProjectionError):
    """Raised when the external state does not match the desired projection."""


@dataclass(frozen=True)
class VisibleFields:
    title: str
    description: str = ""
    checklist: tuple[str, ...] = ()
    managed_comments: tuple[str, ...] = ()


@dataclass(frozen=True)
class TopicProjection:
    topic_id: str
    lesson_number: int
    title: str
    direct_prerequisite_ids: tuple[str, ...] = ()
    content_version: int = 0
    canonical_state: str = "planned"
    materialized: bool = True
    visual_position: int = 0
    managed_fields_version: int = 1
    roadmap_fingerprint: str = ""
    external_id: str | None = None
    external_url: str | None = None
    sync_status: str = "not_started"
    last_synced_at: str | None = None
    lesson_url: str | None = None
    practice_url: str | None = None
    assessment_url: str | None = None
    # Etapa 6d follow-up (task-card-content gap): the engine previously had
    # nowhere to put the human-readable card content instructions/40-
    # publish-tasks.md's "Ready lesson card"/"Future lesson card" sections
    # require -- render_visible_lesson() fell back to a bare Recursos block
    # and a generic 3-item checklist for every lesson, which a real
    # independent evaluate reviewer caught reading a materialized card back
    # from GitHub. These fields are optional so existing callers/tests that
    # never set them keep working; render_visible_lesson() falls back to a
    # generic (but non-empty) placeholder when they are absent, same shape
    # as before this fix, rather than raising.
    learning_summary: str | None = None
    estimated_minutes: int | None = None
    deliverable_summary: str | None = None
    completion_criterion: str | None = None
    session_checklist: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"TOPIC-\d{3,}", self.topic_id):
            raise ValueError(f"invalid topic_id: {self.topic_id}")
        if self.lesson_number < 1:
            raise ValueError("lesson_number must be positive")
        if self.canonical_state not in INTERNAL_STATES:
            raise ValueError(f"invalid canonical_state: {self.canonical_state}")
        if len(self.direct_prerequisite_ids) != len(
            set(self.direct_prerequisite_ids)
        ):
            raise ValueError(f"duplicate prerequisites for {self.topic_id}")
        if self.estimated_minutes is not None and self.estimated_minutes < 1:
            raise ValueError("estimated_minutes must be positive when provided")
        if self.session_checklist and not (3 <= len(self.session_checklist) <= 7):
            raise ValueError(
                "session_checklist must have 3 to 7 items when provided, got "
                f"{len(self.session_checklist)}"
            )


@dataclass(frozen=True)
class ProjectedLesson:
    topic: TopicProjection
    visible_state: str
    ready_role: str | None
    visible: VisibleFields
    internal_metadata: Mapping[str, Any]


@dataclass(frozen=True)
class ProjectionPlan:
    provider: str
    roadmap_fingerprint: str
    lessons: tuple[ProjectedLesson, ...]
    orientation: VisibleFields


@dataclass
class OperationJournal:
    operation_id: str
    provider: str
    operation_type: str = "publication"
    status: str = "not_started"
    attempt: int = 0
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    external_read_count: int = 0
    external_write_count: int = 0
    branch: str | None = None
    pull_request: int | None = None
    commit_budget: int = 1
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    roadmap_fingerprint: str | None = None
    started_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any] | None, *, operation_id: str, provider: str
    ) -> "OperationJournal":
        if not value:
            return cls(operation_id=operation_id, provider=provider)
        if value.get("operation_id") != operation_id:
            raise ProjectionError("resume must preserve the same operation_id")
        if value.get("provider") != provider:
            raise ProjectionError("operation provider cannot change during resume")
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        payload = {key: deepcopy(item) for key, item in value.items() if key in allowed}
        return cls(**payload)

    def checkpoint(self, name: str, **details: Any) -> None:
        now = utc_now()
        self.updated_at = now
        self.checkpoints.append({"name": name, "at": now, **details})

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicationResult:
    integration_state: Mapping[str, Any]
    journal: Mapping[str, Any]
    normalized_snapshot: Mapping[str, Any]
    learner_summary: str


class Backend(Protocol):
    provider: str

    @property
    def write_count(self) -> int: ...

    @property
    def write_log(self) -> Sequence[Mapping[str, Any]]: ...

    def preflight_match(
        self,
        *,
        resource_kind: str,
        durable_external_id: str | None,
        stable_key: str,
        visible_title: str,
    ) -> str | None: ...

    def ensure_container(self, name: str) -> Mapping[str, Any]: ...

    def ensure_managed_sections(self, names: Sequence[str]) -> None: ...

    def upsert_managed_resource(
        self,
        *,
        resource_kind: str,
        stable_key: str,
        durable_external_id: str | None,
        visible: VisibleFields,
        internal_metadata: Mapping[str, Any],
        visible_state: str,
    ) -> Mapping[str, Any]: ...

    def read_normalized_snapshot(self) -> Mapping[str, Any]: ...


@dataclass
class FakeBackend:
    """In-memory adapter used by behavioral tests.

    Unknown sections/resources and student-owned fields are preserved. Internal
    metadata is stored separately from the learner-visible payload.
    """

    provider: str
    container: dict[str, Any] | None = None
    sections: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    _write_log: list[dict[str, Any]] = field(default_factory=list)
    fail_after_writes: int | None = None
    _next_id: int = 1

    def __post_init__(self) -> None:
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unsupported provider: {self.provider}")

    @property
    def write_count(self) -> int:
        return len(self._write_log)

    @property
    def write_log(self) -> Sequence[Mapping[str, Any]]:
        return tuple(deepcopy(self._write_log))

    def _id(self, prefix: str) -> str:
        value = f"{self.provider}-{prefix}-{self._next_id}"
        self._next_id += 1
        return value

    def _write(self, action: str, **details: Any) -> None:
        if self.fail_after_writes is not None and self.write_count >= self.fail_after_writes:
            raise PartialWriteError(f"injected partial failure before {action}")
        self._write_log.append({"action": action, **deepcopy(details)})

    def preflight_match(
        self,
        *,
        resource_kind: str,
        durable_external_id: str | None,
        stable_key: str,
        visible_title: str,
    ) -> str | None:
        if durable_external_id:
            matches = [
                item
                for item in self.resources
                if item.get("id") == durable_external_id
                and item.get("kind") == resource_kind
            ]
            if len(matches) == 1:
                return str(matches[0]["id"])
            if len(matches) > 1:
                raise AmbiguousMatchError(
                    f"duplicate durable external id: {durable_external_id}"
                )

        metadata_matches = [
            item
            for item in self.resources
            if item.get("kind") == resource_kind
            and item.get("internal_metadata", {}).get("stable_key") == stable_key
        ]
        if len(metadata_matches) == 1:
            return str(metadata_matches[0]["id"])
        if len(metadata_matches) > 1:
            raise AmbiguousMatchError(f"ambiguous stable key: {stable_key}")

        title_matches = [
            item
            for item in self.resources
            if item.get("kind") == resource_kind
            and item.get("visible", {}).get("title") == visible_title
        ]
        if len(title_matches) == 1:
            return str(title_matches[0]["id"])
        if len(title_matches) > 1:
            raise AmbiguousMatchError(
                f"ambiguous visible-title match for {visible_title!r}"
            )
        return None

    def ensure_container(self, name: str) -> Mapping[str, Any]:
        if self.container is None:
            self._write("create_container", name=name)
            identifier = self._id("container")
            self.container = {
                "id": identifier,
                "url": f"https://{self.provider}.example/{identifier}",
                "name": name,
            }
        elif self.container.get("name") != name:
            self._write("update_container", name=name)
            self.container["name"] = name
        return deepcopy(self.container)

    def ensure_managed_sections(self, names: Sequence[str]) -> None:
        if self.provider not in ORDERED_PROVIDERS:
            return

        for section in self.sections:
            current = section.get("name")
            if section.get("managed") and current in LEGACY_SECTION_ALIASES:
                new_name = LEGACY_SECTION_ALIASES[str(current)]
                self._write("rename_section", id=section.get("id"), name=new_name)
                section["name"] = new_name

        by_name = {
            str(section.get("name")): section
            for section in self.sections
            if section.get("managed")
        }
        for name in names:
            if name not in by_name:
                self._write("create_section", name=name)
                by_name[name] = {
                    "id": self._id("section"),
                    "name": name,
                    "managed": True,
                }

        unmanaged = [section for section in self.sections if not section.get("managed")]
        desired = [by_name[name] for name in names] + unmanaged
        current_ids = [section.get("id") for section in self.sections]
        desired_ids = [section.get("id") for section in desired]
        if current_ids != desired_ids:
            self._write("reorder_sections", order=list(names))
            self.sections = desired
        elif not self.sections:
            self.sections = desired

    def _resource_by_id(self, identifier: str | None) -> dict[str, Any] | None:
        if not identifier:
            return None
        for item in self.resources:
            if item.get("id") == identifier:
                return item
        return None

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
        identifier = self.preflight_match(
            resource_kind=resource_kind,
            durable_external_id=durable_external_id,
            stable_key=stable_key,
            visible_title=visible.title,
        )
        item = self._resource_by_id(identifier)
        visible_payload = asdict(visible)
        visible_payload["managed_comments"] = list(visible_payload["managed_comments"])
        visible_payload["checklist"] = list(visible_payload["checklist"])
        if item is not None:
            legacy_copy = item.get("student_fields", {}).get("legacy_visible_copy")
            if isinstance(legacy_copy, Mapping):
                legacy_description = str(legacy_copy.get("description") or "").strip()
                if legacy_description and legacy_description not in visible_payload["description"]:
                    visible_payload["description"] += (
                        "\n\n**Conteúdo preservado da projeção anterior**\n\n"
                        + legacy_description
                    )
                for field_name in ("checklist", "managed_comments"):
                    values = legacy_copy.get(field_name)
                    if isinstance(values, list):
                        for value in values:
                            if value and value not in visible_payload[field_name]:
                                visible_payload[field_name].append(value)
        metadata = deepcopy(dict(internal_metadata))
        metadata["stable_key"] = stable_key

        if item is None:
            self._write("create_resource", kind=resource_kind, stable_key=stable_key)
            identifier = self._id(resource_kind)
            item = {
                "id": identifier,
                "url": f"https://{self.provider}.example/{identifier}",
                "kind": resource_kind,
                "managed": True,
                "visible": visible_payload,
                "internal_metadata": metadata,
                "visible_state": visible_state,
                "student_fields": {},
                "student_comments": [],
            }
            self.resources.append(item)
        else:
            changes: dict[str, Any] = {}
            if item.get("visible") != visible_payload:
                changes["visible"] = visible_payload
            if item.get("internal_metadata") != metadata:
                changes["internal_metadata"] = metadata
            if item.get("visible_state") != visible_state:
                changes["visible_state"] = visible_state
            if changes:
                self._write(
                    "update_resource",
                    id=item.get("id"),
                    fields=sorted(changes),
                )
                item.update(changes)
            item["managed"] = True
            item.setdefault("student_fields", {})
            item.setdefault("student_comments", [])

        if self.provider == "github_issues" and resource_kind == "lesson":
            label = GITHUB_STATE_LABELS[visible_state]
            existing_labels = [
                LEGACY_GITHUB_LABELS.get(value, value)
                for value in item.get("labels", [])
                if not str(value).startswith("study:")
            ]
            desired_labels = sorted(set(existing_labels + [label]))
            if item.get("labels") != desired_labels:
                self._write("update_labels", id=item.get("id"), labels=desired_labels)
                item["labels"] = desired_labels

        return deepcopy(item)

    def read_normalized_snapshot(self) -> Mapping[str, Any]:
        return {
            "provider": self.provider,
            "container": deepcopy(self.container),
            "sections": deepcopy(self.sections),
            "resources": deepcopy(self.resources),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def roadmap_fingerprint(topics: Sequence[TopicProjection]) -> str:
    payload = [
        {
            "topic_id": topic.topic_id,
            "lesson_number": topic.lesson_number,
            "title": topic.title,
            "direct_prerequisite_ids": list(topic.direct_prerequisite_ids),
        }
        for topic in sorted(topics, key=lambda item: item.lesson_number)
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def sanitize_known_marker(value: str) -> str:
    """Remove only known historical markers; preserve all unknown copy."""
    return KNOWN_HTML_MARKER.sub("", value).strip()


_URL_SPAN_PATTERN = re.compile(r"https?://\S+")


def validate_visible_fields(
    value: VisibleFields | Mapping[str, Any],
    *,
    allow_topic_id: bool = False,
    own_topic_id: str | None = None,
) -> list[str]:
    """Validate that no managed learner-visible field leaks internal metadata.

    `own_topic_id`, when provided, exempts exactly that topic_id from the
    "internal topic id" check, but only where it appears inside a URL
    substring (e.g. a resource link built from the topic's own real file
    path, such as .../study/modules/TOPIC-001.md) -- never when it appears
    as a bare mention outside a URL. A real Etapa 6d dispatch's readback
    validation blocked every attempt to publish TOPIC-001's Em estudo card
    once it started including real resource links, because TOPIC-001
    predates the slug-filename convention later materializations use and
    its real lesson_url/assessment_url necessarily contain "TOPIC-001" as
    a path segment. That is a legitimate self-referential resource link,
    not a leak of *another* topic's internal ID -- the actual case this
    check exists to catch -- so it must not be flagged. `allow_topic_id`
    (unconditional) is kept separate and unaffected by this narrower
    exemption.
    """
    payload = asdict(value) if isinstance(value, VisibleFields) else dict(value)
    errors: list[str] = []

    def inspect(field_name: str, item: Any) -> None:
        if isinstance(item, str):
            for label, pattern in VISIBLE_METADATA_PATTERNS:
                if label == "internal topic id":
                    if allow_topic_id:
                        continue
                    url_spans = [m.span() for m in _URL_SPAN_PATTERN.finditer(item)]
                    for match in pattern.finditer(item):
                        if own_topic_id and match.group() == own_topic_id and any(
                            start <= match.start() and match.end() <= end
                            for start, end in url_spans
                        ):
                            continue
                        errors.append(f"{field_name} contains {label}")
                        break
                elif pattern.search(item):
                    errors.append(f"{field_name} contains {label}")
        elif isinstance(item, Mapping):
            for key, nested in item.items():
                inspect(f"{field_name}.{key}", nested)
        elif isinstance(item, Iterable) and not isinstance(item, (bytes, bytearray)):
            for index, nested in enumerate(item):
                inspect(f"{field_name}[{index}]", nested)

    for key, item in payload.items():
        inspect(key, item)
    return errors


def _resource_lines(topic: TopicProjection) -> list[str]:
    lines: list[str] = []
    ordered = (
        ("Aula", topic.lesson_url),
        ("Prática", topic.practice_url),
        ("Avaliação", topic.assessment_url),
    )
    for label, url in ordered:
        if url:
            lines.append(f"- **{label}:** {url}")
    return lines


def _learning_summary_or_default(topic: TopicProjection) -> str:
    return topic.learning_summary or f"Praticar e aplicar os conceitos de {topic.title}."


def _estimated_minutes_copy(topic: TopicProjection) -> str:
    return f"{topic.estimated_minutes} minutos" if topic.estimated_minutes else "A definir"


def _deliverable_summary_or_default(topic: TopicProjection) -> str:
    return topic.deliverable_summary or "Aplicar o que foi estudado nesta aula."


def _completion_criterion_or_default(topic: TopicProjection) -> str:
    return (
        topic.completion_criterion
        or "Responder a avaliação de acordo com o critério de aprovação definido."
    )


def _session_checklist_or_default(topic: TopicProjection) -> tuple[str, ...]:
    return topic.session_checklist or (
        "Estudar a aula",
        "Praticar",
        "Enviar a avaliação",
    )


def _rich_lesson_body(topic: TopicProjection, *, intro: str) -> str:
    """Shared body for any lesson card that must show the full learner-facing
    content (Ready lesson card, and Em estudo -- the same materialized lesson
    the learner manually moved, not a different card). A real Etapa 6d
    dispatch's independent reviewer caught the Em estudo card losing this
    content entirely after a republish, even though nothing in
    instructions/40-publish-tasks.md or 41-task-backend-projection.md says
    moving a card to Em estudo should drop its resources, learning summary or
    checklist -- it is the same lesson, just moved by the learner.
    """
    resources = _resource_lines(topic)
    completion_command = f'**"Terminei {topic.title}. Avalie minhas respostas."**'
    return "\n\n".join(
        [
            intro,
            "**O que você vai aprender:** "
            + _learning_summary_or_default(topic)
            + "  \n**Tempo sugerido:** "
            + _estimated_minutes_copy(topic),
            "**Recursos**\n\n" + "\n".join(resources),
            "**O que você vai produzir:** "
            + _deliverable_summary_or_default(topic)
            + "  \n**Para concluir:** "
            + _completion_criterion_or_default(topic),
            "Quando terminar, envie a avaliação e escreva:  \n" + completion_command,
        ]
    )


def render_visible_lesson(topic: TopicProjection, visible_state: str) -> VisibleFields:
    title = f"Aula {topic.lesson_number:02d} · {topic.title}"
    if visible_state in {"Próxima aula", "Disponível em paralelo"}:
        intro = (
            "**Você pode começar por aqui.**"
            if visible_state == "Próxima aula"
            else "**Esta aula também está disponível.**"
        )
        description = _rich_lesson_body(topic, intro=intro)
        checklist = _session_checklist_or_default(topic)
    elif visible_state == "Planejado":
        if topic.direct_prerequisite_ids:
            prerequisite_copy = (
                "Os pré-requisitos diretos desta aula ainda precisam ser concluídos."
            )
        else:
            prerequisite_copy = (
                "A aula completa será preparada quando entrar na janela ativa."
            )
        description = (
            f"**Pré-requisitos desta aula:** {prerequisite_copy}\n\n"
            "A numeração ajuda a localizar a aula; a disponibilidade depende do progresso durável.\n\n"
            "**O que você vai aprender:** "
            + _learning_summary_or_default(topic)
            + "  \n**Tempo sugerido:** "
            + _estimated_minutes_copy(topic)
            + "  \n**O que você vai produzir:** "
            + _deliverable_summary_or_default(topic)
        )
        checklist = ()
    elif visible_state == "Em estudo":
        description = _rich_lesson_body(
            topic, intro="**Aula em estudo.** Use os recursos abaixo e envie a avaliação ao concluir."
        )
        checklist = _session_checklist_or_default(topic)
    elif visible_state == "Em avaliação":
        description = "Avaliação enviada e aguardando correção durável no GitHub."
        checklist = ()
    elif visible_state == "Revisão necessária":
        description = "Revise os pontos indicados na correção e faça a nova tentativa focada."
        checklist = ("Ler a correção", "Refazer a prática focada", "Reenviar")
    else:
        description = "Aula concluída com evidência durável registrada no GitHub."
        checklist = ()
    return VisibleFields(title=title, description=description, checklist=checklist)


def _visible_state_for_non_ready(topic: TopicProjection) -> str | None:
    return {
        "in_progress": "Em estudo",
        "in_assessment": "Em avaliação",
        "review_required": "Revisão necessária",
        "completed": "Concluído",
    }.get(topic.canonical_state)


def build_projection_plan(
    topics: Sequence[TopicProjection], *, provider: str
) -> ProjectionPlan:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider}")
    ordered_all = sorted(topics, key=lambda item: item.lesson_number)
    topic_ids = [topic.topic_id for topic in ordered_all]
    if len(topic_ids) != len(set(topic_ids)):
        raise ValueError("topic_id values must be unique")
    lesson_numbers = [topic.lesson_number for topic in ordered_all]
    if len(lesson_numbers) != len(set(lesson_numbers)):
        raise ValueError("lesson_number values must be unique")

    completed = {
        topic.topic_id
        for topic in ordered_all
        if topic.canonical_state == "completed"
    }
    projected = (
        [topic for topic in ordered_all if topic.materialized]
        if provider == "github_issues"
        else ordered_all
    )
    ready_candidates = [
        topic
        for topic in projected
        if topic.canonical_state in {"planned", "ready"}
        and topic.materialized
        and set(topic.direct_prerequisite_ids).issubset(completed)
    ]
    primary_id = ready_candidates[0].topic_id if ready_candidates else None
    fingerprint = roadmap_fingerprint(ordered_all)
    lessons: list[ProjectedLesson] = []

    for position, topic in enumerate(projected):
        visible_state = _visible_state_for_non_ready(topic)
        ready_role: str | None = None
        if visible_state is None:
            eligible = set(topic.direct_prerequisite_ids).issubset(completed)
            if topic.materialized and eligible:
                if topic.topic_id == primary_id:
                    visible_state = "Próxima aula"
                    ready_role = "primary"
                else:
                    visible_state = "Disponível em paralelo"
                    ready_role = "parallel"
            else:
                visible_state = "Planejado"

        normalized_topic = replace(
            topic,
            visual_position=position,
            roadmap_fingerprint=fingerprint,
        )
        visible = render_visible_lesson(normalized_topic, visible_state)
        internal_metadata = {
            "topic_id": topic.topic_id,
            "visible_lesson_number": topic.lesson_number,
            "direct_prerequisite_ids": list(topic.direct_prerequisite_ids),
            "content_version": topic.content_version,
            "canonical_state": topic.canonical_state,
            "visible_state": visible_state,
            "visual_position": position,
            "managed_fields_version": topic.managed_fields_version,
            "roadmap_fingerprint": fingerprint,
            "ready_role": ready_role,
            "resource_urls": {
                "lesson": topic.lesson_url,
                "practice": topic.practice_url,
                "assessment": topic.assessment_url,
            },
        }
        lessons.append(
            ProjectedLesson(
                topic=normalized_topic,
                visible_state=visible_state,
                ready_role=ready_role,
                visible=visible,
                internal_metadata=internal_metadata,
            )
        )

    orientation = VisibleFields(
        title="📌 Leia antes de começar",
        description=(
            "Use as colunas na ordem Planejado → Disponível em paralelo → Próxima aula → "
            "Em estudo → Em avaliação → Revisão necessária → Concluído. "
            "Mova manualmente somente uma aula disponível para Em estudo. "
            "O GitHub continua sendo a fonte de verdade para conteúdo, avaliação e progresso."
        ),
    )
    return ProjectionPlan(
        provider=provider,
        roadmap_fingerprint=fingerprint,
        lessons=tuple(lessons),
        orientation=orientation,
    )


def _preflight_existing_matches(backend: Backend, plan: ProjectionPlan) -> None:
    backend.preflight_match(
        resource_kind="orientation",
        durable_external_id=None,
        stable_key="orientation",
        visible_title=plan.orientation.title,
    )
    for lesson in plan.lessons:
        backend.preflight_match(
            resource_kind="lesson",
            durable_external_id=lesson.topic.external_id,
            stable_key=lesson.topic.topic_id,
            visible_title=lesson.visible.title,
        )


def _managed_resources(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    resources = snapshot.get("resources")
    if not isinstance(resources, list):
        return []
    return [
        item
        for item in resources
        if isinstance(item, Mapping) and item.get("managed")
    ]


def validate_readback(
    plan: ProjectionPlan, snapshot: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []
    if snapshot.get("provider") != plan.provider:
        errors.append("snapshot provider does not match projection provider")
    container = snapshot.get("container")
    if not isinstance(container, Mapping) or not container.get("id"):
        errors.append("missing task container")

    if plan.provider in ORDERED_PROVIDERS:
        sections = snapshot.get("sections")
        managed_names = [
            item.get("name")
            for item in sections or []
            if isinstance(item, Mapping) and item.get("managed")
        ]
        if managed_names != list(VISIBLE_STATES):
            errors.append("managed list or section order is incorrect")

    managed = _managed_resources(snapshot)
    orientations = [item for item in managed if item.get("kind") == "orientation"]
    lessons = [item for item in managed if item.get("kind") == "lesson"]
    if len(orientations) != 1:
        errors.append("exactly one orientation resource is required")
    if len(lessons) != len(plan.lessons):
        errors.append("lesson resource count does not match the roadmap")

    by_topic: dict[str, Mapping[str, Any]] = {}
    for item in lessons:
        metadata = item.get("internal_metadata")
        topic_id = metadata.get("topic_id") if isinstance(metadata, Mapping) else None
        if not isinstance(topic_id, str):
            errors.append("managed lesson is missing topic_id metadata")
            continue
        if topic_id in by_topic:
            errors.append(f"duplicate managed lesson for {topic_id}")
        by_topic[topic_id] = item

        visible = item.get("visible")
        if isinstance(visible, Mapping):
            errors.extend(
                f"{topic_id}: {message}"
                for message in validate_visible_fields(visible, own_topic_id=topic_id)
            )
        else:
            errors.append(f"{topic_id}: missing visible fields")

    expected_primary = {
        lesson.topic.topic_id
        for lesson in plan.lessons
        if lesson.visible_state == "Próxima aula"
    }
    actual_primary = {
        topic_id
        for topic_id, item in by_topic.items()
        if item.get("visible_state") == "Próxima aula"
    }
    if actual_primary != expected_primary:
        errors.append("primary next lesson does not match the canonical projection")
    if expected_primary and len(actual_primary) != 1:
        errors.append("exactly one unfinished eligible lesson must be Próxima aula")

    expected_parallel = {
        lesson.topic.topic_id
        for lesson in plan.lessons
        if lesson.visible_state == "Disponível em paralelo"
    }
    actual_parallel = {
        topic_id
        for topic_id, item in by_topic.items()
        if item.get("visible_state") == "Disponível em paralelo"
    }
    if actual_parallel != expected_parallel:
        errors.append("parallel eligible lessons do not match the canonical projection")

    for lesson in plan.lessons:
        item = by_topic.get(lesson.topic.topic_id)
        if not item:
            continue
        metadata = item.get("internal_metadata", {})
        if metadata.get("direct_prerequisite_ids") != list(
            lesson.topic.direct_prerequisite_ids
        ):
            errors.append(f"prerequisites differ for {lesson.topic.topic_id}")
        if metadata.get("roadmap_fingerprint") != plan.roadmap_fingerprint:
            errors.append(f"roadmap fingerprint differs for {lesson.topic.topic_id}")
        if item.get("visible_state") != lesson.visible_state:
            errors.append(f"visible state differs for {lesson.topic.topic_id}")

        urls = metadata.get("resource_urls")
        expected_urls = lesson.internal_metadata["resource_urls"]
        if urls != expected_urls:
            errors.append(f"resource URLs differ for {lesson.topic.topic_id}")
        if lesson.topic.materialized and lesson.visible_state != "Planejado":
            for key in ("lesson", "assessment"):
                if not expected_urls.get(key):
                    errors.append(
                        f"materialized eligible lesson {lesson.topic.topic_id} is missing {key} URL"
                    )
        if not lesson.topic.materialized and any(expected_urls.values()):
            errors.append(
                f"unmaterialized lesson {lesson.topic.topic_id} exposes future resource URLs"
            )

    if orientations:
        visible = orientations[0].get("visible")
        if isinstance(visible, Mapping):
            errors.extend(
                f"orientation: {message}"
                for message in validate_visible_fields(visible)
            )
        if orientations[0].get("visible_state") != "Planejado":
            errors.append("orientation resource must remain in Planejado")
    return errors


def normalized_integration_state(
    *,
    plan: ProjectionPlan,
    snapshot: Mapping[str, Any],
    journal: OperationJournal,
    previous_state: Mapping[str, Any] | None = None,
    reminder: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    previous = deepcopy(dict(previous_state or {}))
    container = dict(snapshot.get("container") or {})
    managed = _managed_resources(snapshot)
    lessons = [item for item in managed if item.get("kind") == "lesson"]
    orientation = next(
        (item for item in managed if item.get("kind") == "orientation"), None
    )
    now = utc_now()

    state: dict[str, Any] = {
        "version": 3,
        "source_of_truth": previous.get(
            "source_of_truth",
            {"provider": "github", "repository": "OWNER/REPOSITORY"},
        ),
        "selected_capabilities": {
            **dict(previous.get("selected_capabilities") or {}),
            "task_manager": {
                "provider": plan.provider,
                "status": "success",
                "resolution_status": "resolved",
            },
        },
        "resources": [],
        "projection": {
            "provider": plan.provider,
            "container_id": container.get("id"),
            "container_url": container.get("url"),
            "topic_count": len(plan.lessons),
            "managed_list_order": (
                list(VISIBLE_STATES) if plan.provider in ORDERED_PROVIDERS else None
            ),
            "roadmap_fingerprint": plan.roadmap_fingerprint,
            "readback": {
                "verified_at": now,
                "lesson_card_count": len(lessons),
                "managed_card_count": len(managed),
                "visible_internal_marker_count": 0,
                "external_read_count": journal.external_read_count,
            },
        },
        "operations": {
            journal.operation_id: {
                "status": journal.status,
                "provider": journal.provider,
                "updated_at": journal.updated_at,
                "checkpoint_count": len(journal.checkpoints),
            }
        },
        "resolution": {
            "status": "resolved",
            "unresolved_capabilities": [],
            "validated_at": now,
        },
        "sync": {
            "last_attempt_at": journal.updated_at,
            "last_success_at": now,
            "status": "success",
            "errors": [],
        },
    }

    state["resources"].append(
        {
            "capability": "task_manager",
            "provider": plan.provider,
            "type": "board" if plan.provider == "trello" else "project",
            "id": container.get("id"),
            "url": container.get("url"),
            "sync_status": "success",
            "last_synced_at": now,
        }
    )
    if plan.provider in ORDERED_PROVIDERS:
        for index, name in enumerate(VISIBLE_STATES):
            section = next(
                (
                    item
                    for item in snapshot.get("sections", [])
                    if item.get("managed") and item.get("name") == name
                ),
                {},
            )
            state["resources"].append(
                {
                    "capability": "task_manager",
                    "provider": plan.provider,
                    "type": "list" if plan.provider == "trello" else "section",
                    "id": section.get("id"),
                    "name": name,
                    "position": index,
                    "sync_status": "success",
                    "last_synced_at": now,
                }
            )
    if orientation:
        state["resources"].append(
            {
                "capability": "task_manager",
                "provider": plan.provider,
                "type": "orientation",
                "id": orientation.get("id"),
                "url": orientation.get("url"),
                "canonical_state": "planned",
                "visible_state": "Planejado",
                "sync_status": "success",
                "last_synced_at": now,
            }
        )
    for item in lessons:
        metadata = dict(item.get("internal_metadata") or {})
        state["resources"].append(
            {
                "capability": "task_manager",
                "provider": plan.provider,
                "type": {
                    "trello": "card",
                    "todoist": "task",
                    "github_issues": "issue",
                }[plan.provider],
                "id": item.get("id"),
                "url": item.get("url"),
                "topic_id": metadata.get("topic_id"),
                "visible_lesson_number": metadata.get("visible_lesson_number"),
                "title": item.get("visible", {}).get("title"),
                "direct_prerequisite_ids": metadata.get(
                    "direct_prerequisite_ids", []
                ),
                "content_version": metadata.get("content_version"),
                "canonical_state": metadata.get("canonical_state"),
                "visible_state": item.get("visible_state"),
                "visual_position": metadata.get("visual_position"),
                "managed_fields_version": metadata.get(
                    "managed_fields_version"
                ),
                "roadmap_fingerprint": metadata.get("roadmap_fingerprint"),
                "sync_status": "success",
                "last_synced_at": now,
            }
        )

    if reminder:
        provider = reminder.get("provider")
        status = reminder.get("status")
        state["selected_capabilities"]["reminders"] = {
            "provider": provider,
            "status": status,
            "resolution_status": "resolved" if status == "success" else "failed_optional",
        }
        if status == "success":
            state["resources"].append(
                {
                    "capability": "reminders",
                    "provider": provider,
                    "type": "reminder",
                    "id": reminder.get("id"),
                    "url": reminder.get("url"),
                    "target_url": container.get("url"),
                    "sync_status": "success",
                    "last_synced_at": now,
                }
            )
        else:
            state["sync"]["errors"].append(
                {
                    "capability": "reminders",
                    "status": "failed_optional",
                    "message": reminder.get("error", "optional reminder failed"),
                }
            )
    return state


def render_learner_integration_summary(
    state: Mapping[str, Any], *, routine_mode: str = "none"
) -> str:
    task = dict((state.get("selected_capabilities") or {}).get("task_manager") or {})
    provider = str(task.get("provider") or "ferramenta de tarefas")
    container = next(
        (
            item
            for item in state.get("resources", [])
            if isinstance(item, Mapping)
            and item.get("capability") == "task_manager"
            and item.get("type") in {"board", "project"}
        ),
        {},
    )
    lines = [
        "# Integrações ativas",
        "",
    ]
    # Etapa 6d real finding: this text was unconditionally Kanban/board-style
    # ("Quadro ou projeto", "Use as colunas... mova para Em estudo") for
    # every provider, including github_issues -- which has no board and no
    # columns at all, only issue labels. GitHubIssuesBackend synthesizes a
    # "project"-kind resource for the repository itself (so the `container`
    # lookup above always matches something for github_issues too), which
    # made this read as if a real Kanban board existed when it never did.
    # This was the first time this function's real output was ever
    # inspected against a genuinely successful github_issues projection --
    # every earlier real dispatch either predated a working
    # run_publish_projection call (Etapa 4/5) or had this file hand-written
    # to bypass an unrelated AssertionError bug (Etapa 6a fixture prep).
    if provider == "github_issues":
        lines.extend(
            [
                f"A trilha está organizada nas Issues deste repositório GitHub ({container.get('url', 'link indisponível')}).",
                "",
                "- Cada aula é uma issue; use os labels `study:*` para ver em que estado ela está.",
            ]
        )
    else:
        lines.extend(
            [
                f"A trilha está organizada no **{provider}**.",
                "",
                f"- Quadro ou projeto: {container.get('url', 'link indisponível')}",
                "- Use as colunas para escolher uma aula disponível e mova somente a aula iniciada para **Em estudo**.",
            ]
        )
    reminders = dict((state.get("selected_capabilities") or {}).get("reminders") or {})
    if reminders.get("status") == "success":
        lines.append(
            f"- Lembrete ativo: {reminders.get('provider', 'provedor configurado')}."
        )
    else:
        lines.append("- Nenhum lembrete adicional está ativo.")
    # Etapa 6d real finding: scripts/integration_resolution.py's real
    # validate_plan() requires study.config.yml's own
    # integration_preferences.routine.mode value to appear verbatim
    # somewhere in this text -- but this function only ever receives the
    # projection `state` (built from GitHub Issues + the roadmap), never
    # the instance config file, so it structurally had no way to know that
    # value at all. Etapa 6a's own hand-written fixture happened to
    # include this line by coincidence; the real render function never
    # did until now. routine_mode defaults to "none" because that is the
    # only value this pilot's single real configuration ever uses -- a
    # harness supporting other routine modes would need the caller to
    # read study.config.yml and pass the real value through
    # run_publish_projection instead of relying on this default.
    if routine_mode == "none":
        lines.append(
            "- Rotina de estudo: modo **none** (sem calendário fixo nem lembretes "
            "externos configurados) -- você avança conforme sua disponibilidade."
        )
    else:
        lines.append(f"- Rotina de estudo: modo **{routine_mode}**.")
    lines.extend(
        [
            "- O GitHub continua sendo a fonte de verdade para conteúdo, avaliações e progresso.",
            "",
        ]
    )
    summary = "\n".join(lines)
    if validate_visible_fields({"summary": summary}):
        raise AssertionError("learner integration summary leaked internal metadata")
    return summary


def publish_projection(
    *,
    topics: Sequence[TopicProjection],
    backend: Backend,
    operation_id: str,
    journal_state: Mapping[str, Any] | None = None,
    previous_integration_state: Mapping[str, Any] | None = None,
    course_name: str = "Minha trilha de estudos",
    reminder_writer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    routine_mode: str = "none",
) -> PublicationResult:
    plan = build_projection_plan(topics, provider=backend.provider)
    journal = OperationJournal.from_mapping(
        journal_state, operation_id=operation_id, provider=backend.provider
    )
    now = utc_now()
    journal.attempt += 1
    journal.status = "in_progress"
    journal.started_at = journal.started_at or now
    journal.updated_at = now
    journal.roadmap_fingerprint = plan.roadmap_fingerprint
    journal.checkpoint("preflight_started")

    try:
        _preflight_existing_matches(backend, plan)
        journal.checkpoint("preflight_matches_resolved")

        container = backend.ensure_container(course_name)
        journal.external_write_count = backend.write_count
        journal.checkpoint("container_ready", container_id=container.get("id"))

        backend.ensure_managed_sections(VISIBLE_STATES)
        journal.external_write_count = backend.write_count
        journal.checkpoint("managed_sections_ready")

        backend.upsert_managed_resource(
            resource_kind="orientation",
            stable_key="orientation",
            durable_external_id=None,
            visible=plan.orientation,
            internal_metadata={
                "resource_role": "orientation",
                "managed_fields_version": 1,
                "roadmap_fingerprint": plan.roadmap_fingerprint,
            },
            visible_state="Planejado",
        )
        journal.external_write_count = backend.write_count
        journal.checkpoint("orientation_ready")

        for lesson in plan.lessons:
            backend.upsert_managed_resource(
                resource_kind="lesson",
                stable_key=lesson.topic.topic_id,
                durable_external_id=lesson.topic.external_id,
                visible=lesson.visible,
                internal_metadata=lesson.internal_metadata,
                visible_state=lesson.visible_state,
            )
            journal.external_write_count = backend.write_count
            journal.checkpoint(
                "lesson_ready",
                topic_id=lesson.topic.topic_id,
                visible_state=lesson.visible_state,
            )

        snapshot = backend.read_normalized_snapshot()
        journal.external_read_count += 1
        journal.checkpoint("readback_completed")
        errors = validate_readback(plan, snapshot)
        if errors:
            raise ReadbackValidationError("; ".join(errors))
        journal.checkpoint("readback_validated")

        reminder_result: Mapping[str, Any] | None = None
        if reminder_writer:
            try:
                reminder_result = reminder_writer(container)
                if reminder_result.get("status") != "success":
                    raise RuntimeError(
                        str(reminder_result.get("error") or "optional reminder failed")
                    )
                journal.checkpoint("optional_reminder_succeeded")
            except Exception as exc:  # optional capability is deliberately isolated
                message = str(exc)
                journal.warnings.append(f"optional reminder failed: {message}")
                reminder_result = {
                    "provider": "unknown",
                    "status": "failed_optional",
                    "error": message,
                }
                journal.checkpoint("optional_reminder_failed", error=message)

        journal.status = "success"
        journal.completed_at = utc_now()
        journal.updated_at = journal.completed_at
        integration_state = normalized_integration_state(
            plan=plan,
            snapshot=snapshot,
            journal=journal,
            previous_state=previous_integration_state,
            reminder=reminder_result,
        )
        journal.checkpoint("durable_state_persisted")
        integration_state["operations"][journal.operation_id]["status"] = "success"
        summary = render_learner_integration_summary(integration_state, routine_mode=routine_mode)
        return PublicationResult(
            integration_state=integration_state,
            journal=journal.as_dict(),
            normalized_snapshot=snapshot,
            learner_summary=summary,
        )
    except AmbiguousMatchError as exc:
        journal.status = "blocked"
        journal.errors.append(str(exc))
        journal.updated_at = utc_now()
        journal.checkpoint("blocked_ambiguous_match", error=str(exc))
        raise
    except (PartialWriteError, ReadbackValidationError) as exc:
        journal.status = "partial"
        journal.external_write_count = backend.write_count
        journal.errors.append(str(exc))
        journal.updated_at = utc_now()
        journal.checkpoint("partial_failure", error=str(exc))
        setattr(exc, "journal", journal.as_dict())
        raise


def migrate_legacy_backend(
    *, backend: FakeBackend, topics: Sequence[TopicProjection], operation_id: str
) -> PublicationResult:
    """Idempotently migrate known legacy states and markers, then reconcile."""
    for resource in backend.resources:
        if not resource.get("managed"):
            continue
        visible = resource.get("visible")
        if isinstance(visible, MutableMapping):
            for field_name in ("title", "description"):
                value = visible.get(field_name)
                if isinstance(value, str):
                    visible[field_name] = sanitize_known_marker(value)
            for field_name in ("checklist", "managed_comments"):
                values = visible.get(field_name)
                if isinstance(values, list):
                    visible[field_name] = [
                        sanitize_known_marker(value)
                        if isinstance(value, str)
                        else value
                        for value in values
                    ]
            student_fields = resource.setdefault("student_fields", {})
            if "legacy_visible_copy" not in student_fields:
                student_fields["legacy_visible_copy"] = {
                    "description": str(visible.get("description") or "").strip(),
                    "checklist": [
                        value
                        for value in visible.get("checklist", [])
                        if isinstance(value, str) and value.strip()
                    ],
                    "managed_comments": [
                        value
                        for value in visible.get("managed_comments", [])
                        if isinstance(value, str) and value.strip()
                    ],
                }
        state = resource.get("visible_state")
        if state in LEGACY_SECTION_ALIASES:
            resource["visible_state"] = LEGACY_SECTION_ALIASES[str(state)]
        if backend.provider == "github_issues":
            resource["labels"] = [
                LEGACY_GITHUB_LABELS.get(value, value)
                for value in resource.get("labels", [])
            ]
    return publish_projection(
        topics=topics,
        backend=backend,
        operation_id=operation_id,
    )


def apply_assessment_result(
    topics: Sequence[TopicProjection], *, topic_id: str, passed: bool
) -> tuple[TopicProjection, ...]:
    found = False
    updated: list[TopicProjection] = []
    for topic in topics:
        if topic.topic_id != topic_id:
            updated.append(topic)
            continue
        found = True
        updated.append(
            replace(
                topic,
                canonical_state="completed" if passed else "review_required",
            )
        )
    if not found:
        raise KeyError(topic_id)
    return tuple(updated)


def ensure_focused_review_resource(
    *, backend: Backend, topic: TopicProjection, feedback: str
) -> Mapping[str, Any]:
    visible = VisibleFields(
        title=f"Revisão focada · Aula {topic.lesson_number:02d} · {topic.title}",
        description=feedback,
        checklist=("Revisar a correção", "Praticar o ponto crítico", "Tentar novamente"),
    )
    errors = validate_visible_fields(visible)
    if errors:
        raise ProjectionError("invalid focused review visible copy: " + "; ".join(errors))
    return backend.upsert_managed_resource(
        resource_kind="review",
        stable_key=f"review:{topic.topic_id}:{topic.content_version}",
        durable_external_id=None,
        visible=visible,
        internal_metadata={
            "topic_id": topic.topic_id,
            "content_version": topic.content_version,
            "review_role": "focused_recovery",
            "managed_fields_version": 1,
        },
        visible_state="Revisão necessária",
    )
