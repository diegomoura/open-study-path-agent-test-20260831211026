#!/usr/bin/env python3
"""Offline regressions for scripts/github_issues_backend.py.

The most important case here is `test_publish_projection_round_trip_passes_
readback`: it runs the *real* `task_projection_engine.publish_projection()`
against `GitHubIssuesBackend` backed by an in-memory fake GitHub API, and
asserts `validate_readback` finds zero errors. That is the check that
matters before spending any real API money on a live dispatch -- if the
adapter's shape were wrong (e.g. the internal_metadata caching bug this file
exists to catch), every real run would fail the exact same way, just after
several real, billed tool calls instead of before any.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from github_issues_backend import GitHubIssuesBackend
from task_projection_engine import (
    AmbiguousMatchError,
    TopicProjection,
    publish_projection,
    validate_readback,
    build_projection_plan,
)


class FakeGitHubTransport:
    """In-memory stand-in for agent_runtime.RequestJson, scoped to /issues."""

    def __init__(self) -> None:
        self._issues: dict[int, dict[str, Any]] = {}
        self._next_number = 1
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, path: str, payload: dict[str, Any] | None) -> Any:
        self.calls.append((method, path))
        if method == "GET" and path.startswith("/repos/o/r/issues?"):
            if "page=2" in path:
                return []
            return list(self._issues.values())
        if method == "GET" and path.startswith("/repos/o/r/issues/"):
            number = int(path.rsplit("/", 1)[-1])
            return self._issues[number]
        if method == "POST" and path == "/repos/o/r/issues":
            number = self._next_number
            self._next_number += 1
            issue = {
                "number": number,
                "title": payload["title"],
                "body": payload["body"],
                "labels": [{"name": label} for label in payload.get("labels", [])],
                "html_url": f"https://github.com/o/r/issues/{number}",
            }
            self._issues[number] = issue
            return issue
        if method == "PATCH" and path.startswith("/repos/o/r/issues/"):
            number = int(path.rsplit("/", 1)[-1])
            issue = self._issues[number]
            if "title" in payload:
                issue["title"] = payload["title"]
            if "body" in payload:
                issue["body"] = payload["body"]
            if "labels" in payload:
                issue["labels"] = [{"name": label} for label in payload["labels"]]
            return issue
        raise AssertionError(f"unexpected call: {method} {path}")


def _two_topics() -> list[TopicProjection]:
    return [
        TopicProjection(
            topic_id="TOPIC-001",
            lesson_number=1,
            title="Introdução",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="planned",
            materialized=True,
            lesson_url="https://github.com/o/r/blob/HEAD/study/lessons/aula-01.md",
            assessment_url="https://github.com/o/r/blob/HEAD/study/assessments/aula-01.md",
        ),
        TopicProjection(
            topic_id="TOPIC-002",
            lesson_number=2,
            title="Concorrência",
            direct_prerequisite_ids=("TOPIC-001",),
            content_version=0,
            canonical_state="planned",
            materialized=False,
        ),
    ]


def test_publish_projection_round_trip_passes_readback() -> None:
    transport = FakeGitHubTransport()
    backend = GitHubIssuesBackend(request_json=transport, repository="o/r")
    result = publish_projection(
        topics=_two_topics(),
        backend=backend,
        operation_id="op-1",
        course_name="Go do zero",
    )
    plan = build_projection_plan(_two_topics(), provider="github_issues")
    errors = validate_readback(plan, result.normalized_snapshot)
    assert errors == [], errors
    assert result.journal["status"] == "success"

    # Exactly 2 issues created: one lesson (TOPIC-001 is materialized), one
    # orientation. TOPIC-002 is not materialized -- github_issues never
    # projects unmaterialized topics (build_projection_plan filters them out
    # for this provider specifically).
    created = [c for c in transport.calls if c[0] == "POST"]
    assert len(created) == 2, transport.calls


def test_rerun_with_no_changes_makes_no_write_calls() -> None:
    transport = FakeGitHubTransport()
    backend = GitHubIssuesBackend(request_json=transport, repository="o/r")
    topics = _two_topics()
    publish_projection(topics=topics, backend=backend, operation_id="op-1", course_name="Go do zero")
    writes_first_run = [c for c in transport.calls if c[0] in ("POST", "PATCH")]
    assert writes_first_run, "sanity check: the first run must have written something"

    # Second run, fresh backend instance (simulates a fresh process), but
    # with each topic's external_id threaded back in -- exactly as the
    # harness does by reading state/integrations.json before calling this
    # tool again, per instructions/41-task-backend-projection.md's matching
    # order (durable external ID first).
    snapshot = backend.read_normalized_snapshot()
    external_id_by_topic = {
        item["internal_metadata"]["topic_id"]: item["id"]
        for item in snapshot["resources"]
        if item["kind"] == "lesson"
    }
    topics_with_ids = [
        replace(topic, external_id=external_id_by_topic[topic.topic_id])
        if topic.topic_id in external_id_by_topic
        else topic
        for topic in topics
    ]

    backend2 = GitHubIssuesBackend(request_json=transport, repository="o/r")
    calls_before = len(transport.calls)
    publish_projection(topics=topics_with_ids, backend=backend2, operation_id="op-1", course_name="Go do zero")
    writes_second_run = [c for c in transport.calls[calls_before:] if c[0] in ("POST", "PATCH")]
    assert writes_second_run == [], writes_second_run


def test_ambiguous_title_match_raises_before_any_write() -> None:
    transport = FakeGitHubTransport()
    # Pre-seed two issues sharing the exact title the projection would use,
    # simulating a repo where an unrelated issue collides with a lesson
    # title -- must block, not silently pick one.
    transport._issues[1] = {
        "number": 1,
        "title": "Aula 01 · Introdução",
        "body": "",
        "labels": [],
        "html_url": "https://github.com/o/r/issues/1",
    }
    transport._issues[2] = {
        "number": 2,
        "title": "Aula 01 · Introdução",
        "body": "",
        "labels": [],
        "html_url": "https://github.com/o/r/issues/2",
    }
    transport._next_number = 3
    backend = GitHubIssuesBackend(request_json=transport, repository="o/r")
    try:
        publish_projection(topics=_two_topics(), backend=backend, operation_id="op-1", course_name="Go do zero")
        assert False, "expected AmbiguousMatchError"
    except AmbiguousMatchError:
        pass
    writes = [c for c in transport.calls if c[0] in ("POST", "PATCH")]
    assert writes == [], "must not write anything once a match is ambiguous"


def test_non_study_labels_are_preserved_on_update() -> None:
    transport = FakeGitHubTransport()
    transport._issues[1] = {
        "number": 1,
        "title": "Aula 01 · Introdução",
        "body": "old body",
        "labels": [{"name": "help wanted"}, {"name": "study:planned"}],
        "html_url": "https://github.com/o/r/issues/1",
    }
    transport._next_number = 2
    backend = GitHubIssuesBackend(request_json=transport, repository="o/r")
    publish_projection(topics=_two_topics(), backend=backend, operation_id="op-1", course_name="Go do zero")
    updated_labels = sorted(label["name"] for label in transport._issues[1]["labels"])
    assert "help wanted" in updated_labels
    assert any(label.startswith("study:") for label in updated_labels)
    assert len([label for label in updated_labels if label.startswith("study:")]) == 1


def test_two_simultaneously_eligible_topics_pass_readback() -> None:
    # Real dispatch (Etapa 9 item 2 trilha, evaluate on PR #28 in the
    # disposable pilot repo): the first run in this harness's history with
    # two topics eligible at once (no unmet prerequisites, both
    # materialized) -- TOPIC-002 as "Disponível em paralelo" and TOPIC-003
    # as "Próxima aula" -- failed real readback validation with "primary
    # next lesson does not match the canonical projection" even though the
    # real GitHub writes were correct. Root cause: GITHUB_STATE_LABELS maps
    # both "Disponível em paralelo" and "Próxima aula" to the same
    # study:ready label, and _normalize()'s naive dict-inversion of that
    # many-to-one mapping always resolved back to "Próxima aula" for
    # *every* study:ready issue, collapsing the distinction the read-back
    # check depends on. This never surfaced before because no earlier
    # dispatch in this harness's history had two topics eligible
    # simultaneously.
    transport = FakeGitHubTransport()
    backend = GitHubIssuesBackend(request_json=transport, repository="o/r")
    topics = [
        TopicProjection(
            topic_id="TOPIC-001",
            lesson_number=1,
            title="Introdução",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="completed",
            materialized=True,
            lesson_url="https://github.com/o/r/blob/HEAD/study/lessons/aula-01.md",
            assessment_url="https://github.com/o/r/issues/new?template=assessment-topic-001.yml",
        ),
        TopicProjection(
            topic_id="TOPIC-002",
            lesson_number=2,
            title="Concorrência",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="ready",
            materialized=True,
            lesson_url="https://github.com/o/r/blob/HEAD/study/lessons/aula-02.md",
            assessment_url="https://github.com/o/r/issues/new?template=assessment-topic-002.yml",
        ),
        TopicProjection(
            topic_id="TOPIC-003",
            lesson_number=3,
            title="Testes",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="ready",
            materialized=True,
            lesson_url="https://github.com/o/r/blob/HEAD/study/lessons/aula-03.md",
            assessment_url="https://github.com/o/r/issues/new?template=assessment-topic-003.yml",
        ),
    ]
    result = publish_projection(
        topics=topics,
        backend=backend,
        operation_id="op-1",
        course_name="Go do zero",
    )
    plan = build_projection_plan(topics, provider="github_issues")
    errors = validate_readback(plan, result.normalized_snapshot)
    assert errors == [], errors
    assert result.journal["status"] == "success"

    primary = {lesson.topic.topic_id for lesson in plan.lessons if lesson.visible_state == "Próxima aula"}
    parallel = {lesson.topic.topic_id for lesson in plan.lessons if lesson.visible_state == "Disponível em paralelo"}
    assert len(primary) == 1, plan.lessons
    assert len(parallel) == 1, plan.lessons


def main() -> None:
    tests = [
        test_publish_projection_round_trip_passes_readback,
        test_rerun_with_no_changes_makes_no_write_calls,
        test_ambiguous_title_match_raises_before_any_write,
        test_non_study_labels_are_preserved_on_update,
        test_two_simultaneously_eligible_topics_pass_readback,
    ]
    for test in tests:
        test()
    print(f"github_issues_backend regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
