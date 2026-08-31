#!/usr/bin/env python3
"""Offline regressions for scripts/publish_author_summary.py."""

from __future__ import annotations

from publish_author_summary import render_summary


def test_render_summary_includes_phase_summary_and_next_action() -> None:
    text = render_summary(
        "intake",
        "Two valid candidates found: #9 (Rust) and #10 (TypeScript).",
        "Reply with which issue number to import.",
        False,
        "",
    )
    assert "## Author result (intake)" in text
    assert "Two valid candidates found: #9 (Rust) and #10 (TypeScript)." in text
    assert "**Next action:** Reply with which issue number to import." in text
    assert "No changes needed" not in text


def test_render_summary_handles_missing_fields() -> None:
    text = render_summary("intake", "", "", False, "")
    assert "(no summary provided)" in text
    assert "(no next action provided)" in text


def test_render_summary_surfaces_no_changes_needed_reason() -> None:
    text = render_summary(
        "configure_intake",
        "Everything already configured.",
        "Preencha o formulario.",
        True,
        "Verified form marker, both labels and every instance.yml status field.",
    )
    assert "**No changes needed.**" in text
    assert "Verified form marker, both labels" in text


def main() -> None:
    tests = [
        test_render_summary_includes_phase_summary_and_next_action,
        test_render_summary_handles_missing_fields,
        test_render_summary_surfaces_no_changes_needed_reason,
    ]
    for test in tests:
        test()
    print(f"publish_author_summary regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
