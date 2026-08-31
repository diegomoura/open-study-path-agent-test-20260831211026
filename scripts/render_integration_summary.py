#!/usr/bin/env python3
"""Render the learner-facing integration summary from authoritative state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from task_projection_engine import render_learner_integration_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="state/integrations.json")
    parser.add_argument("--output", default="study/integrations.md")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    state_path = Path(args.state)
    output_path = Path(args.output)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    rendered = render_learner_integration_summary(state)

    if args.check:
        if not output_path.is_file() or output_path.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"{output_path} is inconsistent with {state_path}")
        print(f"{output_path} matches the authoritative integration state.")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"Rendered {output_path} from {state_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
