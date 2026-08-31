#!/usr/bin/env python3
"""Regression checks for diagnostic completion truthfulness."""

from pathlib import Path
import yaml


def main() -> None:
    manifest = yaml.safe_load(Path("instructions/manifest.yml").read_text(encoding="utf-8"))
    diagnostic = next(phase for phase in manifest["phases"] if phase["id"] == "diagnostic")
    expected = "instructions/21-diagnostic-completion-recovery.md"
    if diagnostic.get("execution_contract") != expected:
        raise SystemExit("diagnostic phase is not wired to its completion recovery contract")

    contract = Path(expected).read_text(encoding="utf-8")
    required = [
        "Do not say `Diagnóstico concluído`",
        "status.diagnostic_complete: true",
        "state/diagnostic-summary.json",
        "the pull request was merged",
        "A conversational placement conclusion is provisional",
        "does not continue after the assistant response",
        "Never invent question count",
    ]
    missing = [term for term in required if term not in contract]
    if missing:
        raise SystemExit("missing diagnostic recovery safeguards: " + ", ".join(missing))

    completion = Path("instructions/phase-completion.md").read_text(encoding="utf-8")
    shared_markers = [
        "Finish validation, review, correction, safe merge",
        "Do not merge and do not send a successful phase response",
        "Persisted lifecycle state",
    ]
    missing_shared = [term for term in shared_markers if term not in completion]
    if missing_shared:
        raise SystemExit("shared completion contract lost safeguards: " + ", ".join(missing_shared))

    print("Diagnostic completion recovery regression passed.")


if __name__ == "__main__":
    main()
