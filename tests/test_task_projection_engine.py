from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from task_projection_engine import (  # noqa: E402
    AmbiguousMatchError,
    FakeBackend,
    OperationJournal,
    PartialWriteError,
    ReadbackValidationError,
    TopicProjection,
    VISIBLE_STATES,
    VisibleFields,
    apply_assessment_result,
    build_projection_plan,
    ensure_focused_review_resource,
    migrate_legacy_backend,
    normalized_integration_state,
    publish_projection,
    render_learner_integration_summary,
    render_visible_lesson,
    roadmap_fingerprint,
    validate_readback,
    validate_visible_fields,
)


def topic(
    number: int,
    *,
    prerequisites=(),
    state="planned",
    materialized=True,
    external_id=None,
    title=None,
):
    topic_id = f"TOPIC-{number:03d}"
    return TopicProjection(
        topic_id=topic_id,
        lesson_number=number,
        title=title or f"Tema {number}",
        direct_prerequisite_ids=tuple(prerequisites),
        content_version=1 if materialized else 0,
        canonical_state=state,
        materialized=materialized,
        external_id=external_id,
        lesson_url=(f"https://github.example/aula-{number}" if materialized else None),
        assessment_url=(f"https://github.example/avaliacao-{number}" if materialized else None),
    )


class TaskProjectionEngineTests(unittest.TestCase):
    def base_topics(self):
        return (
            topic(1),
            topic(2),
            topic(3, prerequisites=("TOPIC-001",)),
            topic(4, materialized=False),
        )

    def test_initial_publication_multiple_lessons(self):
        backend = FakeBackend("trello")
        result = publish_projection(
            topics=self.base_topics(), backend=backend, operation_id="publication-v1"
        )
        managed = [
            item
            for item in result.normalized_snapshot["resources"]
            if item.get("managed") and item.get("kind") == "lesson"
        ]
        self.assertEqual(4, len(managed))
        self.assertEqual("success", result.journal["status"])

    def test_exactly_one_primary_and_one_parallel(self):
        plan = build_projection_plan(self.base_topics(), provider="trello")
        primary = [lesson for lesson in plan.lessons if lesson.visible_state == "Próxima aula"]
        parallel = [
            lesson
            for lesson in plan.lessons
            if lesson.visible_state == "Disponível em paralelo"
        ]
        self.assertEqual(["TOPIC-001"], [lesson.topic.topic_id for lesson in primary])
        self.assertEqual(["TOPIC-002"], [lesson.topic.topic_id for lesson in parallel])

    def test_blocked_and_unmaterialized_lessons_remain_planned(self):
        plan = build_projection_plan(self.base_topics(), provider="trello")
        states = {lesson.topic.topic_id: lesson.visible_state for lesson in plan.lessons}
        self.assertEqual("Planejado", states["TOPIC-003"])
        self.assertEqual("Planejado", states["TOPIC-004"])

    def test_orientation_is_not_counted_as_a_lesson(self):
        backend = FakeBackend("todoist")
        result = publish_projection(
            topics=self.base_topics(), backend=backend, operation_id="publication-v1"
        )
        readback = result.integration_state["projection"]["readback"]
        self.assertEqual(4, readback["lesson_card_count"])
        self.assertEqual(5, readback["managed_card_count"])

    def test_second_execution_creates_no_duplicates_or_writes(self):
        backend = FakeBackend("trello")
        first = publish_projection(
            topics=self.base_topics(), backend=backend, operation_id="publication-v1"
        )
        writes = backend.write_count
        second = publish_projection(
            topics=self.base_topics(),
            backend=backend,
            operation_id="publication-v1",
            journal_state=first.journal,
            previous_integration_state=first.integration_state,
        )
        self.assertEqual(writes, backend.write_count)
        lesson_ids = [
            item["id"]
            for item in second.normalized_snapshot["resources"]
            if item.get("kind") == "lesson"
        ]
        self.assertEqual(len(lesson_ids), len(set(lesson_ids)))

    def test_partial_failure_resumes_with_same_operation_id(self):
        backend = FakeBackend("trello", fail_after_writes=5)
        with self.assertRaises(PartialWriteError) as raised:
            publish_projection(
                topics=self.base_topics(),
                backend=backend,
                operation_id="publication-resume-v1",
            )
        journal = raised.exception.journal
        self.assertEqual("partial", journal["status"])
        backend.fail_after_writes = None
        result = publish_projection(
            topics=self.base_topics(),
            backend=backend,
            operation_id="publication-resume-v1",
            journal_state=journal,
        )
        self.assertEqual("publication-resume-v1", result.journal["operation_id"])
        self.assertEqual("success", result.journal["status"])

    def test_existing_resource_is_found_by_durable_id(self):
        durable_id = "trello-lesson-existing"
        backend = FakeBackend(
            "trello",
            resources=[
                {
                    "id": durable_id,
                    "url": "https://trello.example/existing",
                    "kind": "lesson",
                    "managed": True,
                    "visible": {"title": "Old", "description": "", "checklist": [], "managed_comments": []},
                    "internal_metadata": {},
                    "visible_state": "Planejado",
                    "student_fields": {"note": "preserve"},
                    "student_comments": ["my comment"],
                }
            ],
        )
        result = publish_projection(
            topics=(topic(1, external_id=durable_id),),
            backend=backend,
            operation_id="publication-existing-id",
        )
        lessons = [item for item in result.normalized_snapshot["resources"] if item.get("kind") == "lesson"]
        self.assertEqual([durable_id], [item["id"] for item in lessons])
        self.assertEqual("preserve", lessons[0]["student_fields"]["note"])

    def test_unique_title_match_is_adopted_without_durable_id(self):
        backend = FakeBackend(
            "todoist",
            resources=[
                {
                    "id": "todoist-task-existing",
                    "url": "https://todoist.example/existing",
                    "kind": "lesson",
                    "managed": False,
                    "visible": {
                        "title": "Aula 01 · Tema 1",
                        "description": "student text",
                        "checklist": [],
                        "managed_comments": [],
                    },
                    "internal_metadata": {},
                    "visible_state": "Planejado",
                    "student_fields": {"custom": True},
                    "student_comments": [],
                }
            ],
        )
        result = publish_projection(
            topics=(topic(1),), backend=backend, operation_id="publication-unique-match"
        )
        lessons = [item for item in result.normalized_snapshot["resources"] if item.get("kind") == "lesson"]
        self.assertEqual("todoist-task-existing", lessons[0]["id"])
        self.assertTrue(lessons[0]["student_fields"]["custom"])

    def test_ambiguous_match_blocks_all_writes(self):
        duplicate = {
            "url": "https://trello.example/existing",
            "kind": "lesson",
            "managed": False,
            "visible": {
                "title": "Aula 01 · Tema 1",
                "description": "",
                "checklist": [],
                "managed_comments": [],
            },
            "internal_metadata": {},
            "visible_state": "Planejado",
            "student_fields": {},
            "student_comments": [],
        }
        backend = FakeBackend(
            "trello",
            resources=[
                {**deepcopy(duplicate), "id": "duplicate-1"},
                {**deepcopy(duplicate), "id": "duplicate-2"},
            ],
        )
        with self.assertRaises(AmbiguousMatchError):
            publish_projection(
                topics=(topic(1),), backend=backend, operation_id="publication-ambiguous"
            )
        self.assertEqual(0, backend.write_count)

    def test_visible_validator_rejects_html_comment_and_internal_metadata(self):
        fields = VisibleFields(
            title="Aula 01",
            description=(
                '<!-- open-study-path topic_id=TOPIC-001 --> '
                '{"content_version": 1, "roadmap_fingerprint": "abc"}'
            ),
        )
        errors = validate_visible_fields(fields)
        self.assertTrue(any("HTML comment" in error for error in errors))
        self.assertTrue(any("internal topic id" in error for error in errors))
        self.assertTrue(any("content_version" in error for error in errors))

    def test_own_topic_id_inside_own_resource_url_is_not_a_leak(self):
        # Real finding from a real Etapa 6d dispatch: TOPIC-001 predates the
        # slug-filename convention later materializations use, so its real
        # lesson_url/assessment_url necessarily contain "TOPIC-001" as a
        # path segment (study/modules/TOPIC-001.md). Once the Em estudo
        # card started including real resource links, every real dispatch
        # attempt was blocked by this exact check treating a legitimate
        # self-referential resource link as an internal-ID leak. This is
        # not a leak -- it's the topic's own ID inside its own real URL.
        fields = VisibleFields(
            title="Aula 01",
            description=(
                "**Recursos**\n\n"
                "- **Aula:** https://github.com/OWNER/REPO/blob/main/study/modules/TOPIC-001.md\n"
                "- **Avaliação:** https://github.com/OWNER/REPO/blob/main/study/assessments/TOPIC-001.yml"
            ),
        )
        errors = validate_visible_fields(fields, own_topic_id="TOPIC-001")
        self.assertEqual([], errors)

    def test_other_topic_id_inside_a_url_is_still_a_leak(self):
        # The exemption above must stay narrow: a URL containing a
        # *different* topic's internal ID inside another topic's card is
        # exactly the leak the check exists to catch, and must still fail
        # even when own_topic_id is provided for the card being validated.
        fields = VisibleFields(
            title="Aula 01",
            description=(
                "- **Aula:** https://github.com/OWNER/REPO/blob/main/study/modules/TOPIC-002.md"
            ),
        )
        errors = validate_visible_fields(fields, own_topic_id="TOPIC-001")
        self.assertTrue(any("internal topic id" in error for error in errors))

    def test_own_topic_id_outside_a_url_is_still_a_leak(self):
        # The exemption only covers the topic's own ID *inside a URL*. A
        # bare mention of the topic's own ID outside any URL (e.g. leaked
        # into prose) must still be caught.
        fields = VisibleFields(
            title="Aula 01",
            description="Este é o card interno para TOPIC-001, não mostrar ao aluno.",
        )
        errors = validate_visible_fields(fields, own_topic_id="TOPIC-001")
        self.assertTrue(any("internal topic id" in error for error in errors))

    def test_publish_succeeds_with_real_topic_id_shaped_urls(self):
        # End-to-end version of the two unit tests above, through the real
        # publish_projection() -> validate_readback() path with a topic
        # whose real URLs are shaped exactly like TOPIC-001's actual
        # materialized files -- the real dispatch scenario this fix
        # resolves.
        real_shaped_topic = TopicProjection(
            topic_id="TOPIC-001",
            lesson_number=1,
            title="Primeiro programa em Go",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="in_progress",
            materialized=True,
            external_id=None,
            lesson_url="https://github.com/OWNER/REPO/blob/main/study/modules/TOPIC-001.md",
            assessment_url="https://github.com/OWNER/REPO/blob/main/study/assessments/TOPIC-001.yml",
            learning_summary="Explicar a diferença entre rodar e compilar um programa em Go.",
            estimated_minutes=60,
            deliverable_summary="Um programa que compila e roda.",
            completion_criterion="Responder corretamente as questões da avaliação.",
            session_checklist=(
                "Instalar o Go e criar um módulo",
                "Escrever e rodar um primeiro programa",
                "Compilar e executar o binário",
                "Enviar a avaliação",
            ),
        )
        backend = FakeBackend("github_issues")
        result = publish_projection(
            topics=(real_shaped_topic,), backend=backend, operation_id="topic-id-url-v1"
        )
        self.assertEqual("success", result.journal["status"])
        managed = [
            item
            for item in result.normalized_snapshot["resources"]
            if item.get("managed") and item.get("kind") == "lesson"
        ]
        body = managed[0]["visible"]["description"]
        self.assertIn("study/modules/TOPIC-001.md", body)
        self.assertIn("study/assessments/TOPIC-001.yml", body)

    def test_learner_summary_does_not_false_positive_on_repo_name_substring(self):
        # Real finding, documented in Etapa 6a's fixture commit and fixed in
        # Etapa 6d: render_learner_integration_summary() used to raise an
        # uncaught AssertionError whenever the container/project URL
        # contained the literal substring "open-study-path" -- which any
        # repository actually named with that product-name prefix (e.g.
        # this pilot's own disposable test repos) always does in its URL,
        # even though nothing was leaking. The real marker syntax always has
        # a colon immediately after ("open-study-path:topic_id=..."); a bare
        # repository name never does.
        state = {
            "selected_capabilities": {"task_manager": {"provider": "github_issues"}},
            "resources": [
                {
                    "capability": "task_manager",
                    "type": "project",
                    "url": "https://github.com/someone/open-study-path-agent-test-1",
                }
            ],
        }
        summary = render_learner_integration_summary(state)
        self.assertIn("open-study-path-agent-test-1", summary)

        # The real leak this pattern exists to catch must still be caught.
        leaking_state = deepcopy(state)
        leaking_state["resources"][0]["url"] = (
            "https://example.com/<!-- open-study-path:topic_id=TOPIC-001 -->"
        )
        with self.assertRaises(AssertionError):
            render_learner_integration_summary(leaking_state)

    def test_publish_succeeds_for_materialized_topic(self):
        # Regression coverage for run_publish_projection succeeding on a
        # genuinely correct, fully materialized topic with only lesson and
        # assessment resources (study slides were removed entirely; see
        # docs/claude-agent-pilot-etapa10-remove-slides.md).
        materialized_topic = TopicProjection(
            topic_id="TOPIC-001",
            lesson_number=1,
            title="Tema 1",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="ready",
            materialized=True,
            external_id=None,
            lesson_url="https://github.example/aula-1",
            assessment_url="https://github.example/avaliacao-1",
        )
        backend = FakeBackend("github_issues")
        result = publish_projection(
            topics=(materialized_topic,), backend=backend, operation_id="materialized-v1"
        )
        self.assertEqual("success", result.journal["status"])

    def test_learner_summary_uses_label_based_language_for_github_issues(self):
        # Real finding from a real Etapa 6d evaluate dispatch:
        # render_learner_integration_summary()'s text was unconditionally
        # Kanban/board-style ("Quadro ou projeto", "Use as colunas...
        # mova... para Em estudo") for every provider, including
        # github_issues -- which has no board and no columns, only issue
        # labels. GitHubIssuesBackend synthesizes a "project"-kind resource
        # for the repository itself, so the container lookup always
        # matched something for github_issues too, making the rendered
        # text describe a UI that does not exist and would mislead a real
        # learner about how to track their own progress. This was the
        # first time this function's real output was ever produced by a
        # genuinely successful github_issues publish_projection() call --
        # every earlier real dispatch either predated a working
        # run_publish_projection or had this file hand-written to bypass
        # the unrelated AssertionError bug (Etapa 6a fixture prep).
        topic = TopicProjection(
            topic_id="TOPIC-001",
            lesson_number=1,
            title="Tema 1",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="ready",
            materialized=True,
            external_id=None,
            lesson_url="https://github.example/aula-1",
            assessment_url="https://github.example/avaliacao-1",
        )
        backend = FakeBackend("github_issues")
        result = publish_projection(
            topics=(topic,), backend=backend, operation_id="label-language-v1"
        )
        self.assertEqual("success", result.journal["status"])
        summary = result.learner_summary
        self.assertIn("Issues", summary)
        self.assertIn("labels", summary)
        self.assertNotIn("Quadro ou projeto", summary)
        self.assertNotIn("colunas", summary)
        self.assertNotIn("Em estudo", summary)

    def test_learner_summary_mentions_routine_mode(self):
        # Real finding from a real Etapa 6d evaluate dispatch:
        # scripts/integration_resolution.py's real validate_plan() requires
        # study.config.yml's integration_preferences.routine.mode value to
        # appear verbatim in study/integrations.md -- but
        # render_learner_integration_summary() only ever receives the
        # projection state (GitHub + roadmap + journal), never the
        # instance config file, so it structurally had no way to know that
        # value. Etapa 6a's own hand-written fixture happened to include
        # this line by coincidence; the real render function never did
        # until this fix. Defaults to "none" (this pilot's only real
        # value) when the caller does not supply a different one.
        topic = TopicProjection(
            topic_id="TOPIC-001",
            lesson_number=1,
            title="Tema 1",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="ready",
            materialized=True,
            external_id=None,
            lesson_url="https://github.example/aula-1",
            assessment_url="https://github.example/avaliacao-1",
        )
        backend = FakeBackend("github_issues")
        result = publish_projection(
            topics=(topic,), backend=backend, operation_id="routine-mode-v1"
        )
        self.assertIn("none", result.learner_summary.lower())

        backend2 = FakeBackend("github_issues")
        result2 = publish_projection(
            topics=(topic,),
            backend=backend2,
            operation_id="routine-mode-v2",
            routine_mode="fixed_calendar",
        )
        self.assertIn("fixed_calendar", result2.learner_summary)

    def test_readback_fails_when_list_order_is_wrong(self):
        backend = FakeBackend("trello")
        result = publish_projection(
            topics=(topic(1), topic(2)),
            backend=backend,
            operation_id="publication-order",
        )
        snapshot = deepcopy(result.normalized_snapshot)
        managed = [item for item in snapshot["sections"] if item.get("managed")]
        unmanaged = [item for item in snapshot["sections"] if not item.get("managed")]
        snapshot["sections"] = list(reversed(managed)) + unmanaged
        plan = build_projection_plan((topic(1), topic(2)), provider="trello")
        errors = validate_readback(plan, snapshot)
        self.assertTrue(any("order is incorrect" in error for error in errors))

    def test_ready_card_renders_full_instructions_40_contract_shape(self):
        # Real finding from a real Etapa 6d evaluate dispatch: an
        # independent reviewer read a materialized TOPIC-002 issue back
        # from GitHub and found only a bare "Recursos" block and a generic
        # 3-item checklist -- instructions/40-publish-tasks.md's "Ready
        # lesson card" section requires "O que você vai aprender:",
        # "Tempo sugerido:", "O que você vai produzir:", "Para concluir:"
        # and the literal completion-command quote, none of which
        # TopicProjection had fields for. This exercises the full
        # end-to-end publish_projection() -> render_visible_lesson() path
        # with those fields populated the way a real author call must now
        # populate them, and asserts the rendered card body actually
        # contains every required piece -- not just that the function
        # runs without error.
        rich_topic = TopicProjection(
            topic_id="TOPIC-001",
            lesson_number=1,
            title="Tipos e tipagem estática",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="ready",
            materialized=True,
            external_id=None,
            lesson_url="https://github.example/aula-1",
            assessment_url="https://github.example/avaliacao-1",
            learning_summary="Diferenciar tipagem estática de dinâmica na prática.",
            estimated_minutes=45,
            deliverable_summary="Um trecho de código anotado com os tipos corretos.",
            completion_criterion="Acertar pelo menos 4 das 5 questões da avaliação.",
            session_checklist=(
                "Ler a seção sobre tipagem estática",
                "Rodar os três exemplos do módulo",
                "Anotar os tipos no exercício guiado",
                "Enviar a avaliação",
            ),
        )
        backend = FakeBackend("github_issues")
        result = publish_projection(
            topics=(rich_topic,), backend=backend, operation_id="ready-card-contract-v1"
        )
        self.assertEqual("success", result.journal["status"])
        managed = [
            item
            for item in result.normalized_snapshot["resources"]
            if item.get("managed") and item.get("kind") == "lesson"
        ]
        self.assertEqual(1, len(managed))
        body = managed[0]["visible"]["description"]
        self.assertIn("O que você vai aprender", body)
        self.assertIn("Diferenciar tipagem estática de dinâmica na prática.", body)
        self.assertIn("Tempo sugerido", body)
        self.assertIn("45 minutos", body)
        self.assertIn("O que você vai produzir", body)
        self.assertIn("Um trecho de código anotado com os tipos corretos.", body)
        self.assertIn("Para concluir", body)
        self.assertIn("Acertar pelo menos 4 das 5 questões da avaliação.", body)
        self.assertIn(
            '**"Terminei Tipos e tipagem estática. Avalie minhas respostas."**', body
        )
        checklist = managed[0]["visible"]["checklist"]
        self.assertEqual(list(rich_topic.session_checklist), checklist)

    def test_future_card_includes_learning_time_and_deliverable(self):
        # Same instructions/40-publish-tasks.md gap as the ready-card test
        # above, but for the "Future lesson card" section, which also
        # requires "O que você vai aprender:", "Tempo sugerido:" and
        # "O que você vai produzir:" -- the Planejado branch of
        # render_visible_lesson() omitted all three before this fix.
        future_topic = TopicProjection(
            topic_id="TOPIC-002",
            lesson_number=2,
            title="Funções de ordem superior",
            direct_prerequisite_ids=("TOPIC-001",),
            content_version=0,
            canonical_state="planned",
            materialized=False,
            learning_summary="Reconhecer e escrever funções que recebem outras funções.",
            estimated_minutes=30,
            deliverable_summary="Uma função de ordem superior própria, testada.",
        )
        visible = render_visible_lesson(future_topic, "Planejado")
        self.assertIn("O que você vai aprender", visible.description)
        self.assertIn(
            "Reconhecer e escrever funções que recebem outras funções.",
            visible.description,
        )
        self.assertIn("Tempo sugerido", visible.description)
        self.assertIn("30 minutos", visible.description)
        self.assertIn("O que você vai produzir", visible.description)
        self.assertIn(
            "Uma função de ordem superior própria, testada.", visible.description
        )

    def test_ready_card_falls_back_gracefully_without_new_fields(self):
        # Backward compatibility: existing callers/tests (and any real
        # topic contract not yet updated to populate the new optional
        # fields) must not break or produce an empty-looking card --
        # render_visible_lesson() falls back to non-empty generic text
        # for each new field instead of omitting the section or raising.
        plain_topic = topic(1)
        visible = render_visible_lesson(plain_topic, "Próxima aula")
        self.assertIn("O que você vai aprender", visible.description)
        self.assertIn("Tempo sugerido", visible.description)
        self.assertIn("O que você vai produzir", visible.description)
        self.assertIn("Para concluir", visible.description)
        self.assertIn(f'"Terminei {plain_topic.title}.', visible.description)
        self.assertEqual(3, len(visible.checklist))

    def test_session_checklist_length_is_validated(self):
        with self.assertRaises(ValueError):
            TopicProjection(
                topic_id="TOPIC-001",
                lesson_number=1,
                title="Tema 1",
                session_checklist=("Só um passo",),
            )

    def test_in_progress_card_keeps_full_content_after_learner_moves_it(self):
        # Real finding from the real Etapa 6d card-content-fix validation
        # dispatch: an independent reviewer republished TOPIC-001 (already
        # moved by the learner to Em estudo/in_progress) and found the
        # rendered card had regressed to a bare one-line description and a
        # generic 3-item checklist -- nothing in instructions/40-publish-
        # tasks.md or 41-task-backend-projection.md says moving a card to
        # Em estudo should drop its resources, learning summary or
        # checklist; it is the same materialized lesson, just moved by the
        # learner. render_visible_lesson() must keep the full Ready-lesson-
        # card content for Em estudo too.
        in_progress_topic = TopicProjection(
            topic_id="TOPIC-001",
            lesson_number=1,
            title="Primeiro programa em Go",
            direct_prerequisite_ids=(),
            content_version=1,
            canonical_state="in_progress",
            materialized=True,
            external_id=None,
            lesson_url="https://github.example/aula-1",
            assessment_url="https://github.example/avaliacao-1",
            learning_summary="Explicar a diferença entre rodar e compilar um programa em Go.",
            estimated_minutes=60,
            deliverable_summary="Um programa que compila e roda, explicando a diferença.",
            completion_criterion="Responder corretamente as questões sobre compilação e módulos.",
            session_checklist=(
                "Instalar o Go e criar um módulo",
                "Escrever e rodar um primeiro programa",
                "Compilar e executar o binário",
                "Enviar a avaliação",
            ),
        )
        backend = FakeBackend("github_issues")
        result = publish_projection(
            topics=(in_progress_topic,), backend=backend, operation_id="em-estudo-v1"
        )
        self.assertEqual("success", result.journal["status"])
        managed = [
            item
            for item in result.normalized_snapshot["resources"]
            if item.get("managed") and item.get("kind") == "lesson"
        ]
        body = managed[0]["visible"]["description"]
        self.assertIn("O que você vai aprender", body)
        self.assertIn(
            "Explicar a diferença entre rodar e compilar um programa em Go.", body
        )
        self.assertIn("Tempo sugerido", body)
        self.assertIn("60 minutos", body)
        self.assertIn("O que você vai produzir", body)
        self.assertIn("Para concluir", body)
        self.assertIn(
            '**"Terminei Primeiro programa em Go. Avalie minhas respostas."**', body
        )
        checklist = managed[0]["visible"]["checklist"]
        self.assertEqual(list(in_progress_topic.session_checklist), checklist)

    def test_student_sections_resources_comments_and_attachments_are_preserved(self):
        backend = FakeBackend(
            "trello",
            sections=[{"id": "student-list", "name": "Minhas notas", "managed": False}],
            resources=[
                {
                    "id": "student-card",
                    "url": "https://trello.example/student-card",
                    "kind": "note",
                    "managed": False,
                    "visible": {"title": "Meu cartão", "description": "não alterar"},
                    "internal_metadata": {},
                    "visible_state": "Minhas notas",
                    "student_fields": {"attachments": ["file.pdf"]},
                    "student_comments": ["comentário do aluno"],
                }
            ],
        )
        publish_projection(
            topics=(topic(1),), backend=backend, operation_id="publication-preserve"
        )
        student = next(item for item in backend.resources if item["id"] == "student-card")
        self.assertEqual("não alterar", student["visible"]["description"])
        self.assertEqual(["file.pdf"], student["student_fields"]["attachments"])
        self.assertEqual(["comentário do aluno"], student["student_comments"])
        self.assertEqual("Minhas notas", backend.sections[-1]["name"])

    def test_passing_assessment_moves_lesson_and_recomposes_window(self):
        topics = (
            topic(1),
            topic(2),
            topic(3, prerequisites=("TOPIC-001",)),
        )
        updated = apply_assessment_result(topics, topic_id="TOPIC-001", passed=True)
        plan = build_projection_plan(updated, provider="trello")
        states = {lesson.topic.topic_id: lesson.visible_state for lesson in plan.lessons}
        self.assertEqual("Concluído", states["TOPIC-001"])
        self.assertEqual("Próxima aula", states["TOPIC-002"])
        self.assertEqual("Disponível em paralelo", states["TOPIC-003"])

    def test_insufficient_assessment_reuses_focused_review(self):
        backend = FakeBackend("trello")
        target = topic(1)
        first = ensure_focused_review_resource(
            backend=backend, topic=target, feedback="Revise o conceito central."
        )
        writes = backend.write_count
        second = ensure_focused_review_resource(
            backend=backend, topic=target, feedback="Revise o conceito central."
        )
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(writes, backend.write_count)

    def test_roadmap_update_invalidates_and_rewrites_fingerprint(self):
        backend = FakeBackend("trello")
        first_topics = (topic(1), topic(2))
        first = publish_projection(
            topics=first_topics, backend=backend, operation_id="publication-roadmap"
        )
        second_topics = (topic(1), topic(2, title="Tema 2 revisado"), topic(3))
        second = publish_projection(
            topics=second_topics,
            backend=backend,
            operation_id="publication-roadmap",
            journal_state=first.journal,
            previous_integration_state=first.integration_state,
        )
        self.assertNotEqual(
            roadmap_fingerprint(first_topics), roadmap_fingerprint(second_topics)
        )
        self.assertEqual(
            roadmap_fingerprint(second_topics),
            second.integration_state["projection"]["roadmap_fingerprint"],
        )
        lessons = [item for item in backend.resources if item.get("kind") == "lesson"]
        self.assertEqual(3, len(lessons))

    def test_optional_reminder_failure_does_not_undo_board_publication(self):
        backend = FakeBackend("trello")

        def fail_reminder(_container):
            raise RuntimeError("Todoist unavailable")

        result = publish_projection(
            topics=(topic(1),),
            backend=backend,
            operation_id="publication-reminder",
            reminder_writer=fail_reminder,
        )
        self.assertEqual("success", result.journal["status"])
        self.assertTrue(result.journal["warnings"])
        self.assertEqual("success", result.integration_state["sync"]["status"])
        self.assertTrue(result.integration_state["sync"]["errors"])

    def test_migration_is_idempotent_and_removes_only_known_markers(self):
        backend = FakeBackend(
            "trello",
            sections=[
                {"id": "legacy-ready", "name": "Pronto para estudar", "managed": True},
                {"id": "legacy-progress", "name": "Em andamento", "managed": True},
                {"id": "student", "name": "Arquivo pessoal", "managed": False},
            ],
            resources=[
                {
                    "id": "legacy-card",
                    "url": "https://trello.example/legacy",
                    "kind": "lesson",
                    "managed": True,
                    "visible": {
                        "title": "Aula 01 · Tema 1",
                        "description": "Texto útil <!-- open-study-path topic=TOPIC-001 --> manter",
                        "checklist": ["Passo útil"],
                        "managed_comments": ["<!-- open-study-path sync -->", "Comentário conhecido"],
                    },
                    "internal_metadata": {},
                    "visible_state": "Pronto para estudar",
                    "student_fields": {"attachments": ["keep"]},
                    "student_comments": ["<!-- outro marcador desconhecido -->"],
                }
            ],
        )
        first = migrate_legacy_backend(
            backend=backend, topics=(topic(1),), operation_id="migration-v1"
        )
        writes = backend.write_count
        second = migrate_legacy_backend(
            backend=backend, topics=(topic(1),), operation_id="migration-v1"
        )
        self.assertEqual(writes, backend.write_count)
        card = next(item for item in backend.resources if item.get("kind") == "lesson")
        self.assertNotIn("open-study-path", card["visible"]["description"])
        self.assertIn("Texto útil", card["visible"]["description"])
        self.assertEqual(["keep"], card["student_fields"]["attachments"])
        self.assertEqual(
            ["<!-- outro marcador desconhecido -->"], card["student_comments"]
        )
        self.assertEqual(
            [item.get("id") for item in first.integration_state["resources"]],
            [item.get("id") for item in second.integration_state["resources"]],
        )

    def test_github_issues_keeps_legacy_ready_label_and_materialized_scope(self):
        backend = FakeBackend("github_issues")
        topics = (topic(1), topic(2), topic(3, materialized=False))
        result = publish_projection(
            topics=topics, backend=backend, operation_id="publication-github"
        )
        issues = [item for item in backend.resources if item.get("kind") == "lesson"]
        self.assertEqual(2, len(issues))
        labels = {label for item in issues for label in item.get("labels", [])}
        self.assertIn("study:ready", labels)
        self.assertNotIn("study:ready-primary", labels)
        self.assertNotIn("study:ready-parallel", labels)


    def test_complete_trello_fixture_initial_and_assessment_update(self):
        backend = FakeBackend("trello")
        topics = (
            topic(1),
            topic(2),
            topic(3, prerequisites=("TOPIC-001",)),
        )
        initial = publish_projection(
            topics=topics, backend=backend, operation_id="publication-complete-fixture"
        )
        self.assertEqual("success", initial.journal["status"])
        updated_topics = apply_assessment_result(
            topics, topic_id="TOPIC-001", passed=True
        )
        updated = publish_projection(
            topics=updated_topics,
            backend=backend,
            operation_id="publication-complete-fixture",
            journal_state=initial.journal,
            previous_integration_state=initial.integration_state,
        )
        states = {
            item["internal_metadata"].get("topic_id"): item["visible_state"]
            for item in updated.normalized_snapshot["resources"]
            if item.get("kind") == "lesson"
        }
        self.assertEqual("Concluído", states["TOPIC-001"])
        self.assertEqual("Próxima aula", states["TOPIC-002"])
        self.assertEqual("Disponível em paralelo", states["TOPIC-003"])
        self.assertEqual(3, len(states))

    def test_readback_failure_prevents_success_declaration(self):
        class CorruptingBackend(FakeBackend):
            def read_normalized_snapshot(self):
                snapshot = deepcopy(super().read_normalized_snapshot())
                lesson = next(item for item in snapshot["resources"] if item.get("kind") == "lesson")
                lesson["visible"]["description"] += " <!-- open-study-path sync -->"
                return snapshot

        backend = CorruptingBackend("trello")
        with self.assertRaises(ReadbackValidationError) as raised:
            publish_projection(
                topics=(topic(1),),
                backend=backend,
                operation_id="publication-corrupt-readback",
            )
        self.assertEqual("partial", raised.exception.journal["status"])


if __name__ == "__main__":
    unittest.main()
