#!/usr/bin/env python3
"""Compute a stable lesson digest excluding bounded operational projections."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

BLOCKS = (
    ("practice-links", "open-study-path:practice-links"),
    ("task-links", "open-study-path:task-links"),
)


def strip_operational_blocks(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for name, marker in BLOCKS:
        pattern = re.compile(
            rf"^[ \t]*<!--[ \t]*{re.escape(marker)}:start[ \t]*-->.*?"
            rf"^[ \t]*<!--[ \t]*{re.escape(marker)}:end[ \t]*-->[ \t]*(?:\n|$)",
            re.MULTILINE | re.DOTALL,
        )
        matches = list(pattern.finditer(normalized))
        if len(matches) > 1:
            raise ValueError(f"multiple {name} blocks are not allowed")
        normalized = pattern.sub("", normalized)
    normalized = re.sub(r"[ \t]+$", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip() + "\n"


def pedagogical_sha256(text: str) -> str:
    return hashlib.sha256(strip_operational_blocks(text).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lesson", type=Path)
    parser.add_argument("--print-normalized", action="store_true")
    args = parser.parse_args()
    text = args.lesson.read_text(encoding="utf-8")
    if args.print_normalized:
        print(strip_operational_blocks(text), end="")
    else:
        print(pedagogical_sha256(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
