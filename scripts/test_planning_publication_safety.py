#!/usr/bin/env python3
"""Behavioral regressions for topic-first planning and safe publication state."""

from __future__ import annotations

from planning_publication_safety import (
    CALENDAR_PROJECTION_MARKER,
    publication_state_violations,
    topic_first_violations,
)


def config(board: str | None = None) -> dict:
    return {
        "planning": {"unit": "topic"},
        "integrations": {
            "task_manager": {
                "provider": "trello",
                "board_or_project": board,
            }
        },
    }


def test_weekly_availability_does_not_authorize_weekly_structure() -> None:
    roadmap = """# Trilha\n\n- Disponibilidade: 5 horas por semana.\n\n## Projeção semanal\n\n| Semana | Tópicos |\n| --- | --- |\n| 1 | TOPIC-001 |\n"""
    assert topic_first_violations(config(), roadmap)


def test_topic_roadmap_is_allowed() -> None:
    roadmap = """# Trilha\n\n- Esforço total estimado: 55 horas.\n- Ritmo flexível conforme pré-requisitos e progresso.\n\n## Tópicos\n"""
    assert topic_first_violations(config(), roadmap) == []


def test_explicit_calendar_projection_is_allowed_but_not_canonical() -> None:
    roadmap = f"""# Trilha\n\n{CALENDAR_PROJECTION_MARKER}\n## Projeção semanal opcional\n| Semana | Tópicos |\n| --- | --- |\n| 1 | TOPIC-001 |\n"""
    assert topic_first_violations(config(), roadmap) == []


def test_known_board_requires_resource_journal() -> None:
    board = "https://trello.com/b/1WDlmBlM/course"
    state = {"resources": [], "sync": {"status": "partial", "last_attempt_at": None}}
    violations = publication_state_violations(config(board), state)
    assert "configured Trello board is missing from integration resources" in violations
    assert "partial publication must record last_attempt_at" in violations
    assert "partial publication must retain created resources" in violations


def test_recorded_partial_board_is_resumable() -> None:
    board = "https://trello.com/b/1WDlmBlM/course"
    state = {
        "resources": [
            {
                "capability": "tasks",
                "provider": "trello",
                "external_type": "board",
                "external_id": "1WDlmBlM",
                "url": board,
                "status": "partial",
            }
        ],
        "sync": {"status": "partial", "last_attempt_at": "2026-07-28"},
    }
    assert publication_state_violations(config(board), state) == []


def test_disposable_resource_names_are_rejected() -> None:
    state = {
        "resources": [{"provider": "trello", "name": "tmp3"}],
        "sync": {"status": "not_started", "last_attempt_at": None},
    }
    assert "disposable external resource recorded: tmp3" in publication_state_violations(
        config(), state
    )


def main() -> None:
    test_weekly_availability_does_not_authorize_weekly_structure()
    test_topic_roadmap_is_allowed()
    test_explicit_calendar_projection_is_allowed_but_not_canonical()
    test_known_board_requires_resource_journal()
    test_recorded_partial_board_is_resumable()
    test_disposable_resource_names_are_rejected()
    print("Topic-first planning and safe publication regressions passed.")


if __name__ == "__main__":
    main()
