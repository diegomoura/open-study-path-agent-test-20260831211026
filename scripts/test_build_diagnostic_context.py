#!/usr/bin/env python3
"""Offline regressions for scripts/build_diagnostic_context.py."""

from __future__ import annotations

from build_diagnostic_context import render_transcript


def test_render_transcript_with_no_comments_yet() -> None:
    text = render_transcript(42, "Diagnostico: Go do zero", "Contexto original da sessao.", [])
    assert "#42 -- Diagnostico: Go do zero" in text
    assert "Contexto original da sessao." in text
    assert "first turn of the session" in text


def test_render_transcript_includes_every_comment_in_order() -> None:
    comments = [
        {"author_login": "diegomoura", "body": "Resposta 1"},
        {"author_login": "claude-agent-pilot", "body": "Pergunta 2"},
    ]
    text = render_transcript(42, "Diagnostico", "Contexto", comments)
    assert "2 comments" in text
    idx1 = text.index("Resposta 1")
    idx2 = text.index("Pergunta 2")
    assert idx1 < idx2, "comments must stay in chronological order"


def main() -> None:
    tests = [
        test_render_transcript_with_no_comments_yet,
        test_render_transcript_includes_every_comment_in_order,
    ]
    for test in tests:
        test()
    print(f"build_diagnostic_context regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
