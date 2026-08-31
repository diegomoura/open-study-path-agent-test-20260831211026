#!/usr/bin/env python3
"""Offline regressions for the stage-2 agent harness.

None of these tests touch the network or need ANTHROPIC_API_KEY: the transport
is stubbed with a small scripted queue of fake API responses, so we can assert
on the tool-loop mechanics and (most importantly) on the write allowlist
without spending a token.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import json

from agent_runtime import (
    AgentBudgetExceeded,
    AllowlistViolation,
    DEFAULT_MAX_TOKENS,
    INTAKE_AUTHOR_ALLOWED_LABEL,
    MAX_TOOL_ITERATIONS,
    MODEL_PRICING_USD_PER_MTOK,
    PHASE_ALLOWLISTS,
    PHASES_WITH_GITHUB_ISSUES,
    RepoTools,
    author_tools,
    is_write_allowed,
    max_tokens_for,
    max_tool_iterations_for,
    normalize_relative_path,
    resolve_phase_reviewer_model,
    reviewer_tools,
    run_agent,
)
from agent_model_resolution import MODEL_CATALOG


def _default_config(**overrides) -> dict:
    config = {"version": 1, "reasoning_tier": "recommended", "model_overrides": {}}
    config.update(overrides)
    return config


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _tool_use(tool_id: str, name: str, tool_input: dict) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}


def make_scripted_transport(responses: list[list[dict]]):
    """Returns a transport(payload, api_key) that replays `responses` in order."""
    calls: list[dict] = []

    def transport(payload: dict, api_key: str) -> dict:
        calls.append(payload)
        content = responses[len(calls) - 1]
        return {"content": content}

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def test_write_allowlist_matches_setup_execution_contract() -> None:
    assert is_write_allowed("bootstrap_instance", ".open-study-path/instance.yml")
    assert is_write_allowed("bootstrap_instance", "study.config.yml")
    assert not is_write_allowed("bootstrap_instance", "instructions/manifest.yml")
    assert not is_write_allowed("bootstrap_instance", "scripts/agent_runtime.py")
    assert not is_write_allowed("unknown_phase", "study.config.yml")


def test_author_cannot_write_its_own_review_artifact() -> None:
    # instructions/02-setup-execution.md's "Allowed setup diff" lists
    # state/reviews/<setup-operation>.yml, but that path is deliberately
    # excluded from the author's write allowlist in this harness: only the
    # independent reviewer agent (via submit_review, not write_file) may
    # produce a review. See docs/claude-agent-pilot.md.
    assert not is_write_allowed("bootstrap_instance", "state/reviews/setup-v1.yml")
    assert not is_write_allowed("configure_intake", "state/reviews/anything.yml")


def test_normalize_relative_path_rejects_escapes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        try:
            normalize_relative_path(root, "../outside.txt")
            raise AssertionError("expected AllowlistViolation")
        except AllowlistViolation:
            pass
        try:
            normalize_relative_path(root, "/etc/passwd")
            raise AssertionError("expected AllowlistViolation")
        except AllowlistViolation:
            pass


def test_resolve_phase_reviewer_model_inherits_author_tier() -> None:
    recommended = resolve_phase_reviewer_model("bootstrap_instance", _default_config())
    assert recommended == "claude-haiku-4-5-20251001"

    maximum = resolve_phase_reviewer_model("bootstrap_instance", _default_config(reasoning_tier="maximum"))
    assert maximum == "claude-sonnet-5"  # haiku shifted up one tier


def test_author_agent_write_then_finish_happy_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transport = make_scripted_transport(
            [
                [
                    _tool_use(
                        "call_1",
                        "write_file",
                        {"path": "study.config.yml", "content": "owner: test\n"},
                    )
                ],
                [
                    _tool_use(
                        "call_2",
                        "finish_phase",
                        {"summary": "bootstrap complete", "next_action": "run configure_intake"},
                    )
                ],
            ]
        )
        run = run_agent(
            root=root,
            phase="bootstrap_instance",
            role="author",
            model="claude-haiku-4-5-20251001",
            system_prompt="system",
            user_prompt="user",
            transport=transport,
        )
        assert run.finished
        assert run.files_written == ["study.config.yml"]
        assert (root / "study.config.yml").read_text(encoding="utf-8") == "owner: test\n"
        assert run.finish_payload["summary"] == "bootstrap complete"


def test_author_agent_write_outside_allowlist_is_rejected_not_bypassed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "instructions").mkdir()
        (root / "instructions" / "manifest.yml").write_text("version: 1\n", encoding="utf-8")

        transport = make_scripted_transport(
            [
                [
                    _tool_use(
                        "call_1",
                        "write_file",
                        {"path": "instructions/manifest.yml", "content": "tampered: true\n"},
                    )
                ],
                [
                    _tool_use(
                        "call_2",
                        "finish_phase",
                        {"summary": "done", "next_action": "n/a"},
                    )
                ],
            ]
        )
        run = run_agent(
            root=root,
            phase="bootstrap_instance",
            role="author",
            model="claude-haiku-4-5-20251001",
            system_prompt="system",
            user_prompt="user",
            transport=transport,
        )
        # The finish call still succeeds (the model can recover / stop), but the
        # disallowed write must never have reached disk.
        assert run.finished
        assert run.files_written == []
        assert (root / "instructions" / "manifest.yml").read_text(encoding="utf-8") == "version: 1\n"
        # And the rejection must have been reported back as a tool error, not swallowed.
        tool_result_rounds = [entry for entry in run.transcript if entry["role"] == "tool_results"]
        assert tool_result_rounds[0]["content"][0]["is_error"] is True


def test_reviewer_agent_has_no_write_file_tool() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transport = make_scripted_transport(
            [
                [
                    _tool_use(
                        "call_1",
                        "write_file",
                        {"path": "study.config.yml", "content": "sneaky: true\n"},
                    )
                ],
                [
                    _tool_use(
                        "call_2",
                        "submit_review",
                        {
                            "review_yaml": "status: approved\n",
                            "status": "approved",
                            "blocking_findings": [],
                        },
                    )
                ],
            ]
        )
        run = run_agent(
            root=root,
            phase="bootstrap_instance",
            role="reviewer",
            model="claude-haiku-4-5-20251001",
            system_prompt="system",
            user_prompt="user",
            transport=transport,
        )
        assert run.finished
        assert not (root / "study.config.yml").exists()
        assert run.finish_payload["status"] == "approved"


def test_reviewer_cannot_submit_approved_with_blocking_findings() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transport = make_scripted_transport(
            [
                [
                    _tool_use(
                        "call_1",
                        "submit_review",
                        {
                            "review_yaml": "status: approved\n",
                            "status": "approved",
                            "blocking_findings": ["missing label"],
                        },
                    )
                ],
                [
                    _tool_use(
                        "call_2",
                        "submit_review",
                        {
                            "review_yaml": "status: action_required\n",
                            "status": "action_required",
                            "blocking_findings": ["missing label"],
                        },
                    )
                ],
            ]
        )
        run = run_agent(
            root=root,
            phase="bootstrap_instance",
            role="reviewer",
            model="claude-haiku-4-5-20251001",
            system_prompt="system",
            user_prompt="user",
            transport=transport,
        )
        assert run.finished
        assert run.finish_payload["status"] == "action_required"


def test_budget_exceeded_when_agent_never_finishes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # 21 rounds of a no-op tool call, never calling finish_phase.
        responses = [[_tool_use(f"call_{i}", "list_dir", {"path": "."})] for i in range(25)]
        transport = make_scripted_transport(responses)
        try:
            run_agent(
                root=root,
                phase="bootstrap_instance",
                role="author",
                model="claude-haiku-4-5-20251001",
                system_prompt="system",
                user_prompt="user",
                transport=transport,
            )
            raise AssertionError("expected AgentBudgetExceeded")
        except AgentBudgetExceeded:
            pass


def test_stops_cleanly_when_model_returns_no_tool_calls() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transport = make_scripted_transport([[_text_block("I have nothing to do.")]])
        run = run_agent(
            root=root,
            phase="bootstrap_instance",
            role="author",
            model="claude-haiku-4-5-20251001",
            system_prompt="system",
            user_prompt="user",
            transport=transport,
        )
        assert not run.finished
        assert run.finish_payload is None


def test_reviewer_compute_sha256_matches_real_file_hash() -> None:
    import hashlib

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "study.config.yml").write_text("owner: test\n", encoding="utf-8")
        expected = hashlib.sha256(b"owner: test\n").hexdigest()

        transport = make_scripted_transport(
            [
                [_tool_use("call_1", "compute_sha256", {"path": "study.config.yml"})],
                [
                    _tool_use(
                        "call_2",
                        "submit_review",
                        {
                            "review_yaml": f"sha256: {expected}\n",
                            "status": "approved",
                            "blocking_findings": [],
                        },
                    )
                ],
            ]
        )
        run = run_agent(
            root=root,
            phase="bootstrap_instance",
            role="reviewer",
            model="claude-haiku-4-5-20251001",
            system_prompt="system",
            user_prompt="user",
            transport=transport,
        )
        tool_result_rounds = [entry for entry in run.transcript if entry["role"] == "tool_results"]
        hash_result = tool_result_rounds[0]["content"][0]["content"]
        assert hash_result == expected
        assert len(hash_result) == 64  # a real sha256 hex digest, not a model-guessed string


def test_author_agent_has_no_compute_sha256_tool() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transport = make_scripted_transport(
            [
                [_tool_use("call_1", "compute_sha256", {"path": "study.config.yml"})],
                [
                    _tool_use(
                        "call_2",
                        "finish_phase",
                        {"summary": "done", "next_action": "n/a"},
                    )
                ],
            ]
        )
        run = run_agent(
            root=root,
            phase="bootstrap_instance",
            role="author",
            model="claude-haiku-4-5-20251001",
            system_prompt="system",
            user_prompt="user",
            transport=transport,
        )
        tool_result_rounds = [entry for entry in run.transcript if entry["role"] == "tool_results"]
        # dispatch() still recognizes the tool name (shared implementation), but
        # it is never offered in author_tools()'s schema -- a well-behaved model
        # won't call it. If it somehow did, it must not crash the author's run.
        assert run.finished


def test_usage_accumulates_across_tool_round_trips_and_estimates_cost() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        calls = []

        def transport(payload, api_key):
            calls.append(payload)
            if len(calls) == 1:
                return {
                    "content": [_tool_use("call_1", "list_dir", {"path": "."})],
                    "usage": {"input_tokens": 1000, "output_tokens": 50, "cache_creation_input_tokens": 200, "cache_read_input_tokens": 0},
                }
            return {
                "content": [_tool_use("call_2", "finish_phase", {"summary": "done", "next_action": "n/a"})],
                "usage": {"input_tokens": 1300, "output_tokens": 40, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 200},
            }

        run = run_agent(
            root=root,
            phase="bootstrap_instance",
            role="author",
            model="claude-haiku-4-5-20251001",
            system_prompt="system",
            user_prompt="user",
            transport=transport,
        )
        assert run.usage.input_tokens == 2300
        assert run.usage.output_tokens == 90
        assert run.usage.cache_creation_input_tokens == 200
        assert run.usage.cache_read_input_tokens == 200
        # (2300*1.0 + 90*5.0 + 200*1.25 + 200*0.10) / 1_000_000
        expected_cost = (2300 * 1.0 + 90 * 5.0 + 200 * 1.25 + 200 * 0.10) / 1_000_000
        assert abs(run.usage.estimated_cost_usd("claude-haiku-4-5-20251001") - expected_cost) < 1e-12
        assert run.usage.estimated_cost_usd("some-unknown-model") is None


def test_cache_breakpoint_moves_forward_without_mutating_stored_messages() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        captured_payloads = []

        def transport(payload, api_key):
            captured_payloads.append(payload)
            if len(captured_payloads) == 1:
                return {
                    "content": [_tool_use("call_1", "list_dir", {"path": "."})],
                    "usage": {"input_tokens": 500, "output_tokens": 20},
                }
            return {
                "content": [_tool_use("call_2", "finish_phase", {"summary": "done", "next_action": "n/a"})],
                "usage": {"input_tokens": 100, "output_tokens": 15, "cache_read_input_tokens": 500},
            }

        run_agent(
            root=root,
            phase="bootstrap_instance",
            role="author",
            model="claude-haiku-4-5-20251001",
            system_prompt="a fairly long system prompt",
            user_prompt="do the thing",
            transport=transport,
        )

        assert len(captured_payloads) == 2
        # System prompt always carries its own cache breakpoint.
        assert captured_payloads[0]["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert captured_payloads[1]["system"][0]["cache_control"] == {"type": "ephemeral"}

        # First call: only the initial user message exists, so it gets the breakpoint.
        first_messages = captured_payloads[0]["messages"]
        assert first_messages[-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}

        # Second call: the breakpoint moved to the newly-appended tool_results
        # message (round 2's addition), not the original first message.
        second_messages = captured_payloads[1]["messages"]
        assert second_messages[-1]["role"] == "user"
        assert second_messages[-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
        # The first message, now buried earlier in history, must NOT carry a
        # breakpoint on this call -- only content itself should be preserved
        # unmodified (still a plain string, never mutated in place).
        assert second_messages[0]["content"] == "do the thing"


def test_every_pilot_phase_has_an_allowlist() -> None:
    assert "bootstrap_instance" in PHASE_ALLOWLISTS
    assert "configure_intake" in PHASE_ALLOWLISTS
    assert "intake" in PHASE_ALLOWLISTS


def test_intake_allowlist_matches_pull_request_and_merge_contract() -> None:
    # instructions/10-intake.md, "Pull request and merge": limited to the
    # instance marker, study.config.yml and state/intake-summary.json (the
    # fourth item, the review artifact, is never author-writable -- same
    # reasoning as SETUP_ALLOWED_* excluding state/reviews/).
    assert is_write_allowed("intake", ".open-study-path/instance.yml")
    assert is_write_allowed("intake", "study.config.yml")
    assert is_write_allowed("intake", "state/intake-summary.json")
    assert not is_write_allowed("intake", "state/reviews/agent-pilot-intake.yml")
    assert not is_write_allowed("intake", "state/diagnostic-summary.json")
    assert not is_write_allowed("intake", "study/roadmap.md")


def _fake_github_issue_transport(issues: list[dict], label_calls: list[tuple]):
    def transport(method: str, path: str, payload):
        if path.startswith("/repos/o/r/issues?"):
            return issues
        for issue in issues:
            if path == f"/repos/o/r/issues/{issue['number']}" and method == "GET":
                return issue
            if path == f"/repos/o/r/issues/{issue['number']}/labels" and method == "POST":
                label_calls.append((issue["number"], tuple(payload["labels"])))
                return {"ok": True}
        raise AssertionError(f"unexpected GitHub call: {method} {path}")

    return transport


def test_github_issues_tools_are_gated_to_the_intake_phase() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(root=root, phase="bootstrap_instance", role="author")
        try:
            tools.list_intake_issues()
            assert False, "expected AllowlistViolation"
        except AllowlistViolation:
            pass

        assert "list_intake_issues" not in {t["name"] for t in author_tools("bootstrap_instance")}
        assert "list_intake_issues" in {t["name"] for t in author_tools("intake")}
        assert "list_intake_issues" in {t["name"] for t in reviewer_tools("intake")}


def test_resolve_intake_candidates_uses_real_algorithm_not_model_judgment() -> None:
    issues = [
        {
            "number": 5,
            "title": "Aprender Go do zero",
            "labels": [{"name": "study-request"}],
            "user": {"login": "diegomoura"},
            "created_at": "2026-08-14T10:00:00Z",
            "body": "### O que você quer aprender?\n\nGo do zero\n\n### Consentimento\n\n- [x] Concordo",
        },
        {
            "number": 6,
            "title": "",
            "labels": [{"name": "study-request"}],
            "user": {"login": "diegomoura"},
            "created_at": "2026-08-14T11:00:00Z",
            "body": "### O que você quer aprender?\n\nRust\n\n### Consentimento\n\n- [x] Concordo",
        },
    ]
    label_calls: list[tuple] = []
    transport = _fake_github_issue_transport(issues, label_calls)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(root=root, phase="intake", role="author", github_request=transport, github_repository="o/r")
        result = json.loads(
            tools.resolve_intake_candidates(
                expected_headings=["### O que você quer aprender?"],
                required_response_headings=["### O que você quer aprender?"],
                consent_heading="### Consentimento",
            )
        )
        # Issue #6 has no title (missing_course_title) -- rejected
        # deterministically by scripts/intake_resolution.py, not by anything
        # the model decided.
        assert result["state"] == "unique", result
        assert [c["issue_number"] for c in result["accepted"]] == [5]
        rejected_numbers = {c["issue_number"] for c in result["rejected"]}
        assert 6 in rejected_numbers


def test_label_github_issue_refuses_any_label_other_than_imported() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(
            root=root,
            phase="intake",
            role="author",
            github_request=_fake_github_issue_transport([], []),
            github_repository="o/r",
        )
        try:
            tools.label_github_issue(5, "wontfix")
            assert False, "expected AllowlistViolation"
        except AllowlistViolation:
            pass


def test_reviewer_cannot_label_github_issues() -> None:
    assert "label_github_issue" not in {t["name"] for t in reviewer_tools("intake")}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(
            root=root,
            phase="intake",
            role="reviewer",
            github_request=_fake_github_issue_transport([], []),
            github_repository="o/r",
        )
        try:
            tools.label_github_issue(5, INTAKE_AUTHOR_ALLOWED_LABEL)
            assert False, "expected AllowlistViolation"
        except AllowlistViolation:
            pass


def test_intake_summary_write_blocked_without_a_unique_resolution() -> None:
    # Regression for docs/claude-agent-pilot-etapa4.md section 5.2: a real
    # dispatch showed the author writing state/intake-summary.json as an ad
    # hoc status object in the `ambiguous` state instead of leaving it
    # untouched. This must now fail closed, not just be discouraged in the
    # prompt.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(root=root, phase="intake", role="author")

        # Never called resolve_intake_candidates at all.
        try:
            tools.write_file("state/intake-summary.json", "{}")
            assert False, "expected AllowlistViolation"
        except AllowlistViolation:
            pass

        # Simulate an ambiguous resolution, then a none resolution.
        tools._last_candidate_resolution_state = "ambiguous"
        try:
            tools.write_file("state/intake-summary.json", "{}")
            assert False, "expected AllowlistViolation"
        except AllowlistViolation:
            pass

        tools._last_candidate_resolution_state = "none"
        try:
            tools.write_file("state/intake-summary.json", "{}")
            assert False, "expected AllowlistViolation"
        except AllowlistViolation:
            pass

        # A unique resolution allows the write, same as before this guard existed.
        tools._last_candidate_resolution_state = "unique"
        result = tools.write_file("state/intake-summary.json", "{}")
        assert "wrote" in result
        assert (root / "state/intake-summary.json").is_file()

        # The other two domain files were never gated by this check.
        assert tools.write_file("study.config.yml", "version: 2") == "wrote 10 bytes to study.config.yml"


def test_publish_summary_write_blocked_without_success() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(root=root, phase="publish", role="author")
        for path in ("state/integrations.json", "study/integrations.md"):
            try:
                tools.write_file(path, "{}")
                assert False, f"expected AllowlistViolation for {path}"
            except AllowlistViolation:
                pass

        # The operation journal is never gated by publish success -- it must
        # be writable even on a blocked/partial outcome.
        result = tools.write_file("state/operations/op-1.json", "{}")
        assert "wrote" in result

        tools._last_publish_status = "success"
        assert "wrote" in tools.write_file("state/integrations.json", "{}")
        assert "wrote" in tools.write_file("study/integrations.md", "# ok")


def test_publish_tools_are_distinct_from_intake_tools() -> None:
    publish_author_names = {t["name"] for t in author_tools("publish")}
    intake_author_names = {t["name"] for t in author_tools("intake")}
    assert "run_publish_projection" in publish_author_names
    assert "run_publish_projection" not in intake_author_names
    assert "resolve_intake_candidates" not in publish_author_names
    assert "label_github_issue" not in publish_author_names
    # Reviewer for publish gets the same generic read-only issue tools as intake.
    assert "list_intake_issues" in {t["name"] for t in reviewer_tools("publish")}
    assert "run_publish_projection" not in {t["name"] for t in reviewer_tools("publish")}


def test_run_publish_projection_routes_through_dispatch_and_reports_success() -> None:
    from test_github_issues_backend import FakeGitHubTransport

    transport = FakeGitHubTransport()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(root=root, phase="publish", role="author", github_request=transport, github_repository="o/r")
        result_text = tools.dispatch(
            "run_publish_projection",
            {
                "topics": [
                    {
                        "topic_id": "TOPIC-001",
                        "lesson_number": 1,
                        "title": "Introdução",
                        "materialized": True,
                        "lesson_url": "https://github.com/o/r/blob/HEAD/study/lessons/aula-01.md",
                        "assessment_url": "https://github.com/o/r/blob/HEAD/study/assessments/aula-01.md",
                    }
                ],
                "operation_id": "op-1",
                "course_name": "Go do zero",
            },
        )
        result = json.loads(result_text)
        assert result["status"] == "success", result
        assert tools._last_publish_status == "success"
        assert "integration_state" in result and "learner_summary" in result


def test_run_publish_projection_reports_invalid_topic_input_without_crashing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(
            root=root,
            phase="publish",
            role="author",
            github_request=lambda *a, **k: [],
            github_repository="o/r",
        )
        result = json.loads(
            tools.run_publish_projection(
                topics=[{"topic_id": "not-a-valid-id", "lesson_number": 1, "title": "x"}],
                operation_id="op-1",
                course_name="Go do zero",
            )
        )
        assert result["status"] == "error"
        assert result["error_type"] == "InvalidTopicInput"
        assert tools._last_publish_status != "success"


def test_generate_proposal_allowlist_matches_proposal_outputs() -> None:
    # instructions/28-propose-path.md "Outputs": only the roadmap and the
    # instance marker -- everything instructions/30-generate-path.md later
    # materializes (topics, modules, assessments) must stay outside
    # this suboperation's allowlist.
    assert is_write_allowed("generate_proposal", "study/roadmap.md")
    assert is_write_allowed("generate_proposal", ".open-study-path/instance.yml")
    assert not is_write_allowed("generate_proposal", "study/topics/TOPIC-001.md")
    assert not is_write_allowed("generate_proposal", "study/modules/TOPIC-001.md")
    assert not is_write_allowed("generate_proposal", "study/assessments/TOPIC-001.md")
    assert not is_write_allowed("generate_proposal", "state/reviews/agent-pilot-generate-proposal.yml")


def test_generate_proposal_has_no_github_issues_tools() -> None:
    # This suboperation never touches GitHub Issues -- unlike intake/publish,
    # it has no entry in PHASES_WITH_GITHUB_ISSUES and gets only the plain
    # file-writing tool set, same shape as bootstrap_instance/configure_intake.
    author_names = {t["name"] for t in author_tools("generate_proposal")}
    assert author_names == {"read_file", "list_dir", "write_file", "finish_phase"}
    reviewer_names = {t["name"] for t in reviewer_tools("generate_proposal")}
    assert reviewer_names == {"read_file", "list_dir", "compute_sha256", "submit_review"}


def test_pricing_table_covers_every_resolvable_model() -> None:
    # Regression for a real bug found during Etapa 5's first real dispatch
    # (docs/claude-agent-pilot-etapa5.md): MODEL_PRICING_USD_PER_MTOK had
    # "claude-opus-5" as a key while agent_model_resolution.MODEL_CATALOG
    # resolves the "opus" tier to "claude-opus-4-8" -- a silent key mismatch
    # that made every Opus-tier run's estimated_cost_usd come back None
    # instead of erroring loudly. This test would have caught it before any
    # real dispatch spent money blind to its own cost.
    for tier, model in MODEL_CATALOG.items():
        assert model in MODEL_PRICING_USD_PER_MTOK, (
            f"MODEL_PRICING_USD_PER_MTOK is missing an entry for {model!r} "
            f"(tier {tier!r}) -- estimated_cost_usd will silently come back "
            "None for every run using this model"
        )


def test_generate_detailed_allowlist_covers_expected_outputs() -> None:
    assert is_write_allowed("generate_detailed", "study/topics/TOPIC-001.md")
    assert is_write_allowed("generate_detailed", "study/modules/TOPIC-001.md")
    assert is_write_allowed("generate_detailed", "study/assessments/TOPIC-001.md")
    assert is_write_allowed("generate_detailed", "state/content-reviews/TOPIC-001.yml")
    assert is_write_allowed("generate_detailed", ".github/ISSUE_TEMPLATE/assessment-topic-001.yml")
    assert is_write_allowed("generate_detailed", "study/roadmap.md")
    assert is_write_allowed("generate_detailed", "study/integrations.md")
    # Prefix matching must not spill onto unrelated Issue Form files --
    # confirms the intake form is never shadowed by this phase's allowlist.
    assert not is_write_allowed("generate_detailed", ".github/ISSUE_TEMPLATE/create-study-path.yml")


def test_generate_detailed_gets_a_higher_tool_iteration_budget() -> None:
    # Regression for a real dispatch finding (docs/claude-agent-pilot-
    # etapa5.md, section 7): the default 20-iteration budget, tuned for
    # smaller phases, was too tight for generate_detailed's realistic
    # workload (read ~4 input files, write ~5-6 outputs) and a real author
    # run hit "did not call its finish tool" before completing. Other
    # phases keep the original, tighter budget -- a runaway loop there
    # should still be caught quickly.
    assert max_tool_iterations_for("generate_detailed") > MAX_TOOL_ITERATIONS
    assert max_tool_iterations_for("intake") == MAX_TOOL_ITERATIONS
    assert max_tool_iterations_for("publish") == MAX_TOOL_ITERATIONS
    assert max_tool_iterations_for("some_unknown_phase") == MAX_TOOL_ITERATIONS


def test_agent_budget_exceeded_carries_tool_call_diagnostics() -> None:
    # Regression for the same Etapa 5b dispatch finding as the budget test
    # above: when the budget runs out, the exception must carry which tools
    # were called (and on what path/number) so a human can tell real,
    # varied progress apart from a repeated/looping pattern -- "did not call
    # its finish tool" alone doesn't distinguish those.
    def transport(payload, api_key):
        return {
            "content": [
                {"type": "tool_use", "id": "1", "name": "write_file", "input": {"path": "study/topics/TOPIC-001.md", "content": "x"}}
            ]
        }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        try:
            run_agent(
                root=root,
                phase="intake",  # small budget (20) so this finishes quickly
                role="author",
                model="claude-haiku-4-5-20251001",
                system_prompt="sp",
                user_prompt="up",
                api_key="key",
                transport=transport,
            )
            assert False, "expected AgentBudgetExceeded"
        except AgentBudgetExceeded as exc:
            assert len(exc.tool_call_names) == MAX_TOOL_ITERATIONS
            assert exc.tool_call_names[0] == "write_file(study/topics/TOPIC-001.md)"


def test_transcript_captures_stop_reason_for_unfinished_runs() -> None:
    # Regression for the second real Etapa 5b dispatch finding: the model
    # can stop producing tool_use blocks (loop breaks early, run.finished
    # stays False) without ever hitting the iteration budget. stop_reason
    # is what distinguishes "response got truncated" from "the model just
    # stopped" -- it must survive into the transcript for main() to log it.
    def transport(payload, api_key):
        return {"content": [{"type": "text", "text": "I'm done here."}], "stop_reason": "end_turn"}

    with tempfile.TemporaryDirectory() as tmp:
        run = run_agent(
            root=Path(tmp),
            phase="intake",
            role="author",
            model="claude-haiku-4-5-20251001",
            system_prompt="sp",
            user_prompt="up",
            api_key="key",
            transport=transport,
        )
        assert run.finished is False
        assert run.transcript[-1]["stop_reason"] == "end_turn"
        assert run.transcript[-1]["content"][0]["text"] == "I'm done here."


def test_generate_detailed_gets_a_higher_max_tokens_budget() -> None:
    # Regression for the real dispatch that revealed this: the reviewer,
    # writing a full curriculum review artifact against a real materialized
    # lesson, hit stop_reason "max_tokens" at the 4096 default -- truncated
    # mid-turn before producing a complete tool_use block. Other phases keep
    # the original, smaller cap.
    assert max_tokens_for("generate_detailed") > DEFAULT_MAX_TOKENS
    assert max_tokens_for("intake") == DEFAULT_MAX_TOKENS
    assert max_tokens_for("publish") == DEFAULT_MAX_TOKENS
    assert max_tokens_for("some_unknown_phase") == DEFAULT_MAX_TOKENS


def test_diagnostic_allowlist_matches_pull_request_policy() -> None:
    assert is_write_allowed("diagnostic", ".open-study-path/instance.yml")
    assert is_write_allowed("diagnostic", "state/diagnostic-summary.json")
    assert not is_write_allowed("diagnostic", "state/reviews/agent-pilot-diagnostic.yml")
    assert not is_write_allowed("diagnostic", "study/roadmap.md")


def test_diagnostic_author_gets_comment_tools_reviewer_does_not() -> None:
    author_names = {t["name"] for t in author_tools("diagnostic")}
    assert "list_issue_comments" in author_names
    assert "post_issue_comment" in author_names
    assert "run_publish_projection" not in author_names

    reviewer_names = {t["name"] for t in reviewer_tools("diagnostic")}
    assert "list_issue_comments" not in reviewer_names
    assert "post_issue_comment" not in reviewer_names
    assert "read_github_issue" not in reviewer_names  # excluded even though phase is in PHASES_WITH_GITHUB_ISSUES


def test_diagnostic_finish_phase_requires_a_posted_comment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(
            root=root,
            phase="diagnostic",
            role="author",
            github_request=lambda *a, **k: {},
            github_repository="o/r",
        )
        try:
            tools.finish_phase("asked question 1", "waiting for reply")
            assert False, "expected AllowlistViolation"
        except AllowlistViolation:
            pass

        tools.post_issue_comment(5, "Qual sua experiencia com Go?")
        result = tools.finish_phase("asked question 1", "waiting for reply")
        assert result == "phase marked finished"


def test_diagnostic_finish_phase_guard_does_not_apply_to_other_phases() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(root=root, phase="bootstrap_instance", role="author")
        # No comment was posted (bootstrap_instance has no such tool at all)
        # -- finish_phase must still work normally for every other phase.
        assert tools.finish_phase("done", "next") == "phase marked finished"


def test_diagnostic_post_issue_comment_appends_loop_prevention_marker() -> None:
    from agent_runtime import DIAGNOSTIC_AUTHOR_COMMENT_MARKER

    posted: dict[str, object] = {}

    def fake_request(method, path, payload):
        posted["method"] = method
        posted["path"] = path
        posted["payload"] = payload
        return {}

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(
            root=root,
            phase="diagnostic",
            role="author",
            github_request=fake_request,
            github_repository="o/r",
        )
        tools.post_issue_comment(5, "Pergunta 1: como vai?")
        body = posted["payload"]["body"]
        assert body.startswith("Pergunta 1: como vai?")
        assert DIAGNOSTIC_AUTHOR_COMMENT_MARKER in body
        # Idempotent: calling again with a body that already carries the
        # marker (e.g. a retried call) must not duplicate it.
        tools.post_issue_comment(5, body)
        assert posted["payload"]["body"].count(DIAGNOSTIC_AUTHOR_COMMENT_MARKER) == 1


def test_non_diagnostic_post_issue_comment_never_gets_the_marker() -> None:
    from agent_runtime import DIAGNOSTIC_AUTHOR_COMMENT_MARKER

    posted: dict[str, object] = {}

    def fake_request(method, path, payload):
        posted["payload"] = payload
        return {}

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(
            root=root,
            phase="intake",
            role="author",
            github_request=fake_request,
            github_repository="o/r",
        )
        tools.list_intake_issues()  # populate _issue_summaries so label calls don't explode
        tools.post_issue_comment(5, "comentario qualquer")
        assert DIAGNOSTIC_AUTHOR_COMMENT_MARKER not in posted["payload"]["body"]


def test_configure_intake_finish_phase_accepts_no_changes_needed_with_reason() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(root=root, phase="configure_intake", role="author")
        result = tools.finish_phase(
            "Already fully configured",
            "Preencha o formulario.",
            no_changes_needed=True,
            reason="Verified form marker, both labels and every instance.yml status field.",
        )
        assert result == "phase marked finished"
        assert tools.finish_payload["no_changes_needed"] is True
        assert "form marker" in tools.finish_payload["reason"]


def test_configure_intake_finish_phase_rejects_no_changes_needed_without_reason() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(root=root, phase="configure_intake", role="author")
        try:
            tools.finish_phase("summary", "next", no_changes_needed=True, reason="   ")
            assert False, "expected AllowlistViolation"
        except AllowlistViolation:
            pass


def test_no_changes_needed_is_rejected_outside_its_phase_allowlist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # intake's ambiguous/no-candidate case must keep failing the workflow's
        # no-diff guard, not gain a way to opt out of it.
        tools = RepoTools(
            root=root,
            phase="intake",
            role="author",
            github_request=lambda *a, **k: {},
            github_repository="o/r",
        )
        try:
            tools.finish_phase("summary", "next", no_changes_needed=True, reason="looks fine")
            assert False, "expected AllowlistViolation"
        except AllowlistViolation:
            pass


def test_finish_phase_default_always_sets_no_changes_needed_false() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools = RepoTools(root=root, phase="bootstrap_instance", role="author")
        tools.finish_phase("done", "next")
        assert tools.finish_payload["no_changes_needed"] is False
        assert tools.finish_payload["reason"] == ""


def test_no_changes_needed_tool_property_only_offered_to_allowed_phases() -> None:
    def finish_phase_schema(phase: str) -> dict:
        tool = next(t for t in author_tools(phase) if t["name"] == "finish_phase")
        return tool["input_schema"]["properties"]

    assert "no_changes_needed" in finish_phase_schema("configure_intake")
    assert "no_changes_needed" not in finish_phase_schema("intake")
    assert "no_changes_needed" not in finish_phase_schema("bootstrap_instance")


def test_diagnostic_gets_a_higher_max_tokens_budget() -> None:
    # Regression for a real dispatch finding (Etapa 4b validation): the
    # diagnostic reviewer hit stop_reason "max_tokens" at the untouched 4096
    # default -- this phase was missing from PHASE_MAX_TOKENS entirely when
    # it was first introduced, the same class of bug generate_detailed had.
    assert max_tokens_for("diagnostic") > DEFAULT_MAX_TOKENS


def test_track_allowlist_matches_progress_review_profile() -> None:
    # Copied directly from review_framework.py's
    # phase_allows_artifact("progress") -- see agent_runtime.py's
    # TRACK_ALLOWED_* comment (Etapa 6a).
    assert is_write_allowed("track", "state/progress.json")
    assert is_write_allowed("track", "state/integrations.json")
    assert not is_write_allowed("track", "study/roadmap.md")
    assert not is_write_allowed("track", ".open-study-path/instance.yml")
    assert not is_write_allowed("track", "state/reviews/agent-pilot-track.yml")
    assert not is_write_allowed("track", "state/assessments/TOPIC-001/attempt-001.json")


def test_track_gets_only_the_narrow_read_github_issue_tool() -> None:
    author_tool_names = {t["name"] for t in author_tools("track")}
    reviewer_tool_names = {t["name"] for t in reviewer_tools("track")}

    assert "read_github_issue" in author_tool_names
    assert "read_github_issue" in reviewer_tool_names
    # The intake-scoped discovery-label listing must never leak into track:
    # it lists issues by DISCOVERY_LABEL, which has nothing to do with a
    # topic's authoritative task issue.
    assert "list_intake_issues" not in author_tool_names
    assert "list_intake_issues" not in reviewer_tool_names
    # No write-side GitHub tools -- track only ever reads issue state.
    assert "label_github_issue" not in author_tool_names
    assert "post_issue_comment" not in author_tool_names
    assert "run_publish_projection" not in author_tool_names


def test_track_reviewer_model_inherits_the_author_haiku_tier() -> None:
    # AGENT_CATALOG registers "track" itself as its own author agent id
    # (Etapa 6a) -- PHASE_AUTHOR_AGENT["track"] == "track" -- so the generic
    # phase_review pass inherits whatever tier that row resolves to, same
    # "herda o tier da fase" rule as every other phase without a dedicated
    # reviewer row.
    config = _default_config()
    assert resolve_phase_reviewer_model("track", config) == MODEL_CATALOG["haiku"]


def test_replan_allowlist_matches_review_framework_profile() -> None:
    # Copied directly from review_framework.py's phase_allows_artifact
    # ("replan") -- see agent_runtime.py's REPLAN_ALLOWED_* comment
    # (Etapa 6b).
    assert is_write_allowed("replan", ".open-study-path/instance.yml")
    assert is_write_allowed("replan", "study.config.yml")
    assert is_write_allowed("replan", "state/progress.json")
    assert is_write_allowed("replan", "study/roadmap.md")
    assert is_write_allowed("replan", "study/topics/TOPIC-003/module.md")
    assert is_write_allowed(
        "replan", ".github/ISSUE_TEMPLATE/assessment-topic-003.yml"
    )
    assert not is_write_allowed("replan", "state/integrations.json")
    assert not is_write_allowed("replan", "state/assessments/TOPIC-001/attempt-001.json")
    assert not is_write_allowed("replan", "state/reviews/agent-pilot-replan.yml")


def test_replan_has_no_github_issues_tools() -> None:
    # instructions/60-replan.md never touches GitHub Issues directly -- only
    # repository files. Unlike track, replan should not appear in
    # PHASES_WITH_GITHUB_ISSUES and should get none of the GitHub-specific
    # tool names on either role.
    assert "replan" not in PHASES_WITH_GITHUB_ISSUES
    author_tool_names = {t["name"] for t in author_tools("replan")}
    reviewer_tool_names = {t["name"] for t in reviewer_tools("replan")}
    github_tool_names = {
        "list_intake_issues",
        "read_github_issue",
        "label_github_issue",
        "post_issue_comment",
        "run_publish_projection",
    }
    assert not (author_tool_names & github_tool_names)
    assert not (reviewer_tool_names & github_tool_names)


def test_replan_reviewer_model_is_sonnet_per_agent_catalog() -> None:
    # AGENT_CATALOG already had a "replan" row (Sonnet) before Etapa 6b --
    # unlike track, there was no catalog gap to close here, only harness
    # wiring. The generic phase_review pass inherits it the same way.
    config = _default_config()
    assert resolve_phase_reviewer_model("replan", config) == MODEL_CATALOG["sonnet"]


def test_replan_gets_a_higher_tool_iteration_and_token_budget() -> None:
    # Regression for a real dispatch finding (Etapa 6b validation): the
    # first real replan run failed outright with "did not finish within 20
    # tool round trips" at the untouched MAX_TOOL_ITERATIONS default --
    # replan was missing from PHASE_MAX_TOOL_ITERATIONS entirely, the same
    # class of gap diagnostic and generate_detailed already hit before it.
    assert max_tool_iterations_for("replan") > MAX_TOOL_ITERATIONS
    assert max_tokens_for("replan") > DEFAULT_MAX_TOKENS


def test_evaluate_allowlist_matches_full_assessment_profile() -> None:
    # Etapa 6d: expanded to match review_framework.py's full
    # phase_allows_artifact("assessment") scope, now that materialization
    # and the task-state move are wired -- see agent_runtime.py's
    # EVALUATE_ALLOWED_* comment. Etapa 6c's version of this test asserted
    # the opposite (narrower) scope; that assertion is now stale by design,
    # not a regression. state/content-reviews/ and state/operations/ are
    # additionally allowed here even though phase_allows_artifact("assessment")
    # itself doesn't cover them -- both are real gaps a real dispatch hit:
    # the reviewer blocked on a missing content-review artifact, and the
    # author refused to journal a failed run_publish_projection attempt
    # because the prefix wasn't allowed.
    assert is_write_allowed("evaluate", "state/progress.json")
    assert is_write_allowed("evaluate", "state/integrations.json")
    assert is_write_allowed("evaluate", "state/assessments/TOPIC-002/attempt-001.json")
    assert is_write_allowed("evaluate", "study/roadmap.md")
    assert is_write_allowed("evaluate", "study/integrations.md")
    assert is_write_allowed("evaluate", "study/topics/TOPIC-003/module.md")
    assert is_write_allowed("evaluate", "study/modules/TOPIC-003.md")
    assert is_write_allowed("evaluate", "study/flashcards/TOPIC-003.md")
    assert is_write_allowed("evaluate", "study/assessments/TOPIC-003.yml")
    assert is_write_allowed("evaluate", ".github/ISSUE_TEMPLATE/assessment-topic-003.yml")
    assert is_write_allowed("evaluate", "state/content-reviews/TOPIC-003.yml")
    assert is_write_allowed("evaluate", "state/operations/assessment-topic-003-attempt-01.json")
    assert not is_write_allowed("evaluate", "state/reviews/agent-pilot-evaluate.yml")
    assert not is_write_allowed("evaluate", ".open-study-path/instance.yml")


def test_evaluate_gets_the_full_resolution_and_publish_tool_set() -> None:
    author_tool_names = {t["name"] for t in author_tools("evaluate")}
    reviewer_tool_names = {t["name"] for t in reviewer_tools("evaluate")}

    for name in (
        "list_assessment_issues",
        "resolve_assessment_candidates",
        "read_github_issue",
        "post_issue_comment",
        "label_github_issue",
        "unlabel_github_issue",
    ):
        assert name in author_tool_names, name

    # Reviewer gets the same two read-only resolution tools plus
    # read_github_issue for independent re-verification, but never the
    # publish-side-effect tools -- same "reviewer cannot cause the side
    # effect it is checking" rule as every other phase.
    assert "list_assessment_issues" in reviewer_tool_names
    assert "resolve_assessment_candidates" in reviewer_tool_names
    assert "read_github_issue" in reviewer_tool_names
    assert "post_issue_comment" not in reviewer_tool_names
    assert "label_github_issue" not in reviewer_tool_names
    assert "unlabel_github_issue" not in reviewer_tool_names
    # Never the intake-scoped bundle -- list_intake_issues filters by the
    # discovery label, unrelated to assessment issues.
    assert "list_intake_issues" not in author_tool_names
    assert "list_intake_issues" not in reviewer_tool_names
    # Etapa 6d: author now has the task-projection engine access needed to
    # move a mastered topic's authoritative task to Concluído.
    assert "run_publish_projection" in author_tool_names
    assert "apply_topic_assessment_result" in author_tool_names
    # Reviewer still never gets the publish-side-effect tools -- same
    # "reviewer cannot cause the side effect it is checking" rule as every
    # other phase, unchanged from Etapa 6c.
    assert "run_publish_projection" not in reviewer_tool_names
    assert "apply_topic_assessment_result" not in reviewer_tool_names


def test_evaluate_label_tools_are_scoped_to_exact_labels() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        reviewer = RepoTools(root=root, phase="evaluate", role="reviewer")
        try:
            reviewer.label_github_issue(1, "assessment:graded")
        except AllowlistViolation as exc:
            assert "not available to this role" in str(exc)
        else:
            raise AssertionError("reviewer must never be allowed to label an issue")

        author = RepoTools(
            root=root,
            phase="evaluate",
            role="author",
            github_request=lambda *a, **k: {},
            github_repository="o/r",
        )
        try:
            author.label_github_issue(1, "intake:imported")
        except AllowlistViolation as exc:
            assert "only" in str(exc)
        else:
            raise AssertionError("evaluate author must not be able to apply an unrelated label")
        try:
            author.unlabel_github_issue(1, "assessment:graded")
        except AllowlistViolation as exc:
            assert "only" in str(exc)
        else:
            raise AssertionError("evaluate author must only be able to remove assessment:submitted")


def test_evaluate_author_can_actually_read_the_submitted_answers() -> None:
    # Regression for a real dispatch finding (Etapa 6c validation): the
    # first real evaluate run correctly refused to grade rather than
    # fabricate a score, because resolve_assessment_candidates only returns
    # the classification decision (accepted/rejected + reasons), never the
    # issue body -- and read_github_issue was missing from the author's
    # tool list entirely. list_assessment_issues alone only returns
    # metadata (number, title, labels, author, date), never the answers.
    author_tool_names = {t["name"] for t in author_tools("evaluate")}
    assert "read_github_issue" in author_tool_names


def test_evaluate_reviewer_model_is_sonnet_and_structural() -> None:
    # AGENT_CATALOG already had an "evaluate" row (Sonnet, structural=True)
    # before Etapa 6c -- no catalog gap to close here, only harness wiring,
    # same as replan.
    config = _default_config()
    assert resolve_phase_reviewer_model("evaluate", config) == MODEL_CATALOG["sonnet"]


def test_apply_topic_assessment_result_transforms_canonical_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        author = RepoTools(root=root, phase="evaluate", role="author")
        topics = [
            {
                "topic_id": "TOPIC-001",
                "lesson_number": 1,
                "title": "Primeiro programa em Go",
                "direct_prerequisite_ids": [],
                "content_version": 1,
                "canonical_state": "ready",
                "materialized": True,
                "visual_position": 0,
                "external_id": "21",
                "lesson_url": "https://example.com/lesson",
            }
        ]

        mastered = json.loads(author.apply_topic_assessment_result(topics, "TOPIC-001", True))
        assert mastered["status"] == "success"
        assert mastered["topics"][0]["canonical_state"] == "completed"

        not_mastered = json.loads(author.apply_topic_assessment_result(topics, "TOPIC-001", False))
        assert not_mastered["topics"][0]["canonical_state"] == "review_required"

        unknown = json.loads(author.apply_topic_assessment_result(topics, "TOPIC-999", True))
        assert unknown["status"] == "error"
        assert unknown["error_type"] == "UnknownTopicId"

        reviewer = RepoTools(root=root, phase="evaluate", role="reviewer")
        try:
            reviewer.apply_topic_assessment_result(topics, "TOPIC-001", True)
        except AllowlistViolation as exc:
            assert "not available to this role" in str(exc)
        else:
            raise AssertionError("reviewer must never be able to apply an assessment result")


def test_evaluate_gets_a_higher_tool_iteration_and_token_budget() -> None:
    # Applied preemptively (Etapa 6c) rather than waiting for a failed real
    # dispatch, unlike replan -- diagnostic, generate_detailed and replan
    # all independently hit the same untouched-default gap first.
    assert max_tool_iterations_for("evaluate") > MAX_TOOL_ITERATIONS
    assert max_tokens_for("evaluate") > DEFAULT_MAX_TOKENS


def test_generate_proposal_gets_a_higher_tool_iteration_and_token_budget() -> None:
    # Etapa 9 item 2: a real dispatch (never real-dispatch-validated before
    # this) hit "did not finish within 20 tool round trips" and failed
    # outright -- same untouched-default gap generate_detailed, diagnostic
    # and replan each independently hit first.
    assert max_tool_iterations_for("generate_proposal") > MAX_TOOL_ITERATIONS
    assert max_tokens_for("generate_proposal") > DEFAULT_MAX_TOKENS


def main() -> None:
    tests = [
        test_write_allowlist_matches_setup_execution_contract,
        test_author_cannot_write_its_own_review_artifact,
        test_normalize_relative_path_rejects_escapes,
        test_resolve_phase_reviewer_model_inherits_author_tier,
        test_author_agent_write_then_finish_happy_path,
        test_author_agent_write_outside_allowlist_is_rejected_not_bypassed,
        test_reviewer_agent_has_no_write_file_tool,
        test_reviewer_cannot_submit_approved_with_blocking_findings,
        test_reviewer_compute_sha256_matches_real_file_hash,
        test_author_agent_has_no_compute_sha256_tool,
        test_usage_accumulates_across_tool_round_trips_and_estimates_cost,
        test_cache_breakpoint_moves_forward_without_mutating_stored_messages,
        test_budget_exceeded_when_agent_never_finishes,
        test_stops_cleanly_when_model_returns_no_tool_calls,
        test_every_pilot_phase_has_an_allowlist,
        test_intake_allowlist_matches_pull_request_and_merge_contract,
        test_github_issues_tools_are_gated_to_the_intake_phase,
        test_resolve_intake_candidates_uses_real_algorithm_not_model_judgment,
        test_label_github_issue_refuses_any_label_other_than_imported,
        test_reviewer_cannot_label_github_issues,
        test_intake_summary_write_blocked_without_a_unique_resolution,
        test_publish_summary_write_blocked_without_success,
        test_publish_tools_are_distinct_from_intake_tools,
        test_run_publish_projection_routes_through_dispatch_and_reports_success,
        test_run_publish_projection_reports_invalid_topic_input_without_crashing,
        test_generate_proposal_allowlist_matches_proposal_outputs,
        test_generate_proposal_has_no_github_issues_tools,
        test_pricing_table_covers_every_resolvable_model,
        test_generate_detailed_allowlist_covers_expected_outputs,
        test_generate_detailed_gets_a_higher_tool_iteration_budget,
        test_agent_budget_exceeded_carries_tool_call_diagnostics,
        test_transcript_captures_stop_reason_for_unfinished_runs,
        test_generate_detailed_gets_a_higher_max_tokens_budget,
        test_diagnostic_allowlist_matches_pull_request_policy,
        test_diagnostic_author_gets_comment_tools_reviewer_does_not,
        test_diagnostic_finish_phase_requires_a_posted_comment,
        test_diagnostic_finish_phase_guard_does_not_apply_to_other_phases,
        test_diagnostic_post_issue_comment_appends_loop_prevention_marker,
        test_non_diagnostic_post_issue_comment_never_gets_the_marker,
        test_configure_intake_finish_phase_accepts_no_changes_needed_with_reason,
        test_configure_intake_finish_phase_rejects_no_changes_needed_without_reason,
        test_no_changes_needed_is_rejected_outside_its_phase_allowlist,
        test_finish_phase_default_always_sets_no_changes_needed_false,
        test_no_changes_needed_tool_property_only_offered_to_allowed_phases,
        test_diagnostic_gets_a_higher_max_tokens_budget,
        test_track_allowlist_matches_progress_review_profile,
        test_track_gets_only_the_narrow_read_github_issue_tool,
        test_track_reviewer_model_inherits_the_author_haiku_tier,
        test_replan_allowlist_matches_review_framework_profile,
        test_replan_has_no_github_issues_tools,
        test_replan_reviewer_model_is_sonnet_per_agent_catalog,
        test_replan_gets_a_higher_tool_iteration_and_token_budget,
        test_evaluate_allowlist_matches_full_assessment_profile,
        test_evaluate_gets_the_full_resolution_and_publish_tool_set,
        test_evaluate_author_can_actually_read_the_submitted_answers,
        test_evaluate_label_tools_are_scoped_to_exact_labels,
        test_evaluate_reviewer_model_is_sonnet_and_structural,
        test_apply_topic_assessment_result_transforms_canonical_state,
        test_evaluate_gets_a_higher_tool_iteration_and_token_budget,
        test_generate_proposal_gets_a_higher_tool_iteration_and_token_budget,
    ]
    for test in tests:
        test()
    print(f"Agent runtime regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
