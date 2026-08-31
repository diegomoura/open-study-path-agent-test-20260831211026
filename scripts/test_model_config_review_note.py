#!/usr/bin/env python3
"""Behavioral regressions for persisting structural model-tier warnings."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from model_config_review_note import active_config_path, render_note, write_or_remove_note

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "templates" / "agent-models.yml"


def _write_config(directory: Path, **overrides: str | None) -> Path:
    document = {
        "version": 1,
        "reasoning_tier": "recommended",
        "model_overrides": {
            "curriculum_architect": None,
            "content_author": None,
            "evaluate": None,
            "bootstrap": None,
        },
    }
    document["model_overrides"].update(overrides)
    path = directory / "models.yml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_template_default_produces_no_warnings_and_no_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "state" / "reviews" / "model-config-warnings.md"
        summary = write_or_remove_note("bootstrap_instance", TEMPLATE_PATH, out_path)
        assert "No structural model-tier warnings" in summary
        assert not out_path.is_file()


def test_structural_override_below_recommended_writes_note() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config_path = _write_config(Path(tmp), curriculum_architect="haiku")
        out_path = Path(tmp) / "state" / "reviews" / "model-config-warnings.md"
        summary = write_or_remove_note("generate_proposal", config_path, out_path)
        assert "Wrote 1 structural model-tier warning" in summary
        content = out_path.read_text(encoding="utf-8")
        assert "curriculum_architect" in content
        assert "generate_proposal" in content


def test_mechanical_override_below_recommended_writes_no_note() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config_path = _write_config(Path(tmp), bootstrap="haiku")  # already the floor tier
        out_path = Path(tmp) / "state" / "reviews" / "model-config-warnings.md"
        summary = write_or_remove_note("bootstrap_instance", config_path, out_path)
        assert "No structural model-tier warnings" in summary
        assert not out_path.is_file()


def test_stale_note_is_removed_once_warnings_clear() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "state" / "reviews" / "model-config-warnings.md"
        warned_config = _write_config(Path(tmp), content_author="haiku")
        write_or_remove_note("generate_detailed", warned_config, out_path)
        assert out_path.is_file()

        clean_config = _write_config(Path(tmp), content_author=None)
        write_or_remove_note("generate_detailed", clean_config, out_path)
        assert not out_path.is_file()


def test_render_note_lists_every_warning() -> None:
    text = render_note("evaluate", ["warning one", "warning two"], TEMPLATE_PATH)
    assert "- warning one" in text
    assert "- warning two" in text
    assert "evaluate" in text


def test_active_config_path_prefers_instance_file_when_present() -> None:
    # Uses the real repository paths: in this checkout .open-study-path/models.yml
    # does not exist (it is instance-only state), so this must resolve to the
    # template. This also guards against the template file itself disappearing.
    assert active_config_path() == TEMPLATE_PATH


def main() -> None:
    tests = [
        test_template_default_produces_no_warnings_and_no_file,
        test_structural_override_below_recommended_writes_note,
        test_mechanical_override_below_recommended_writes_no_note,
        test_stale_note_is_removed_once_warnings_clear,
        test_render_note_lists_every_warning,
        test_active_config_path_prefers_instance_file_when_present,
    ]
    for test in tests:
        test()
    print(f"Model config review note regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
