#!/usr/bin/env python3
"""Persist non-blocking structural model-tier warnings for a real dispatch.

`scripts/validate_model_config.py` already prints structural warnings (a
structural agent configured below its recommended tier) when run by hand, but
that output never reached `state/reviews/`, so it was invisible on any actual
agent-pilot dispatch (see docs/agent-model-configuration.md, "Próximos
passos"). This script closes that gap: it resolves whichever configuration a
real dispatch is actually using (the instance's `.open-study-path/models.yml`
if present, otherwise the all-recommended template) and writes the warnings,
if any, to a review artifact next to the rest of that dispatch's review state.

Idempotent and side-effect-free beyond the one output file: if there are no
structural warnings, any stale warning file from an earlier dispatch is
removed rather than left around with outdated content.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from agent_model_resolution import resolve_effective_models, structural_warnings

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "templates" / "agent-models.yml"
INSTANCE_PATH = ROOT / ".open-study-path" / "models.yml"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    return value if isinstance(value, dict) else {}


def active_config_path() -> Path:
    return INSTANCE_PATH if INSTANCE_PATH.is_file() else TEMPLATE_PATH


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def render_note(phase: str, warnings: list[str], config_path: Path) -> str:
    lines = [
        "# Structural model-tier warning",
        "",
        f"Phase: `{phase}`. Configuration source: `{_display_path(config_path)}`.",
        "",
        (
            "One or more agents classified as structural "
            "(`scripts/agent_model_resolution.py`, `STRUCTURAL_AGENTS`) are configured "
            "below their recommended tier. This is not blocking -- it may be a "
            "deliberate cost/quality trade-off -- but it is recorded here so it is "
            "visible on this dispatch's pull request rather than silent."
        ),
        "",
    ]
    lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    return "\n".join(lines)


def write_or_remove_note(phase: str, config_path: Path, out_path: Path) -> str:
    """Write the warning note, or remove a stale one. Returns a human-readable summary."""
    config = load_yaml(config_path)
    resolved = resolve_effective_models(config)
    warnings = structural_warnings(resolved)

    if not warnings:
        if out_path.is_file():
            out_path.unlink()
        return "No structural model-tier warnings for this dispatch."

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_note(phase, warnings, config_path), encoding="utf-8")
    return f"Wrote {len(warnings)} structural model-tier warning(s) to {out_path}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, help="Manifest phase this dispatch is running")
    parser.add_argument(
        "--out",
        default=str(ROOT / "state" / "reviews" / "model-config-warnings.md"),
        help="Where to write the warning note (removed if there are no warnings)",
    )
    args = parser.parse_args()

    print(write_or_remove_note(args.phase, active_config_path(), Path(args.out)))


if __name__ == "__main__":
    main()
