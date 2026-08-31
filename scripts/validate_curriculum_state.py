#!/usr/bin/env python3
"""Validate curriculum proposal and generation state in the current repository."""

from __future__ import annotations

from pathlib import Path
import sys

from curriculum_state import validate_repository

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    errors = validate_repository(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Curriculum proposal and generation state passed.")


if __name__ == "__main__":
    main()
