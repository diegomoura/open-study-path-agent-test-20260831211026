#!/usr/bin/env python3
"""Offline regressions for scripts/bridge_diagnostic_answer.py, using a fake API."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from diagnostic_answer_resolution import ANSWER_LABEL, IMPORTED_LABEL, SESSION_LABEL
from ensure_repository_labels import ApiError


class FakeApi:
    """Minimal fake of RequestJson covering exactly what bridge_diagnostic_answer.py calls."""

    def __init__(self, issues: dict[int, dict]):
        self.issues = issues
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method: str, path: str, payload: dict | None):
        self.calls.append((method, path, payload))
        if method == "GET" and "/issues/" in path:
            tail = path.rsplit("/issues/", 1)[-1]
            if tail.isdigit():
                number = int(tail)
                if number not in self.issues:
                    raise ApiError(404, "not found")
                return self.issues[number]
        if method == "POST" and path.endswith("/comments"):
            return {"id": 1}
        if method == "POST" and path.endswith("/labels"):
            return {}
        if method == "PATCH":
            return {}
        raise AssertionError(f"unexpected call: {method} {path}")


def _issue(number: int, body: str, labels: list[str], is_pr: bool = False) -> dict:
    payload = {
        "number": number,
        "title": "x",
        "body": body,
        "labels": [{"name": name} for name in labels],
        "user": {"login": "learner"},
    }
    if is_pr:
        payload["pull_request"] = {}
    return payload


def _run_bridge(fake: FakeApi, answer_issue_number: int, github_output_path: str | None = None) -> None:
    import bridge_diagnostic_answer as bridge

    original_factory = bridge.github_request_factory
    bridge.github_request_factory = lambda token, api_url: fake
    try:
        sys.argv = [
            "bridge_diagnostic_answer.py",
            "--repository",
            "example/study",
            "--answer-issue-number",
            str(answer_issue_number),
        ]
        import os

        os.environ["GITHUB_TOKEN"] = "fake-token"
        if github_output_path is not None:
            os.environ["GITHUB_OUTPUT"] = github_output_path
        elif "GITHUB_OUTPUT" in os.environ:
            del os.environ["GITHUB_OUTPUT"]
        bridge.main()
    finally:
        bridge.github_request_factory = original_factory


def test_accepted_submission_comments_labels_closes_and_outputs_session_number() -> None:
    import os
    import tempfile

    answer_body = (
        "### Número da issue da sua sessão de diagnóstico\n\n5\n\n"
        "### Resposta à Pergunta 1\n\nresposta um\n"
    )
    fake = FakeApi(
        {
            9: _issue(9, answer_body, [ANSWER_LABEL]),
            5: _issue(5, "session body", [SESSION_LABEL]),
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        output_path = os.path.join(tmp, "github_output")
        open(output_path, "w", encoding="utf-8").close()
        _run_bridge(fake, 9, github_output_path=output_path)
        output_content = open(output_path, encoding="utf-8").read()
        assert "session_issue_number=5" in output_content

    comment_calls = [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/comments")]
    assert len(comment_calls) == 1
    assert comment_calls[0][1] == "/repos/example/study/issues/5/comments"
    assert "resposta um" in comment_calls[0][2]["body"]

    label_calls = [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/labels")]
    assert len(label_calls) == 1
    assert label_calls[0][1] == "/repos/example/study/issues/9/labels"
    assert label_calls[0][2]["labels"] == [IMPORTED_LABEL]

    patch_calls = [c for c in fake.calls if c[0] == "PATCH"]
    assert len(patch_calls) == 1
    assert patch_calls[0][2] == {"state": "closed"}

    # Never tries to trigger a separate workflow run -- see the module
    # docstring for why (both a repost-only and an explicit
    # workflow_dispatch call were tried for real and both failed).
    dispatch_calls = [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/dispatches")]
    assert not dispatch_calls


def test_rejected_submission_only_comments_on_answer_issue() -> None:
    # No session_issue_number field at all.
    answer_body = "### Resposta à Pergunta 1\n\nresposta um\n"
    fake = FakeApi({9: _issue(9, answer_body, [ANSWER_LABEL])})
    _run_bridge(fake, 9)

    comment_calls = [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/comments")]
    assert len(comment_calls) == 1
    assert comment_calls[0][1] == "/repos/example/study/issues/9/comments"

    assert not [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/labels")]
    assert not [c for c in fake.calls if c[0] == "PATCH"]


def test_session_issue_not_found_is_rejected_not_a_crash() -> None:
    answer_body = (
        "### Número da issue da sua sessão de diagnóstico\n\n404\n\n"
        "### Resposta à Pergunta 1\n\nresposta um\n"
    )
    fake = FakeApi({9: _issue(9, answer_body, [ANSWER_LABEL])})
    _run_bridge(fake, 9)

    comment_calls = [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/comments")]
    assert len(comment_calls) == 1
    assert "404" in comment_calls[0][2]["body"] or "não foi encontrada" in comment_calls[0][2]["body"]


def main() -> None:
    tests = [
        test_accepted_submission_comments_labels_closes_and_outputs_session_number,
        test_rejected_submission_only_comments_on_answer_issue,
        test_session_issue_not_found_is_rejected_not_a_crash,
    ]
    for test in tests:
        test()
    print(f"Diagnostic answer bridge regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
