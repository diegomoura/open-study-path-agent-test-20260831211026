#!/usr/bin/env python3
"""Write the author agent's summary/next_action to the GitHub Actions job summary.

Kept as its own script, not an inline multi-line `python -c` in the workflow
YAML, for the same reason scripts/format_pr_body.py is its own script:
embedding multi-line Python inside a `run:` block is what caused real YAML
bugs during this pilot's first dispatches (see docs/claude-agent-pilot.md).

Runs unconditionally, *before* the "Fail if the author produced no diff"
step in .github/workflows/agent-pilot-setup.yml -- so an author result that
correctly reports an ambiguous/none intake classification (and therefore
writes nothing) still leaves its explanation visible on the run's summary
page, instead of being silently lost when the job then fails on purpose.
Before this existed, the only trace of *why* a no-diff run failed was the
generic "author agent finished without writing any allowed file" error --
the actual candidate list and next action the model produced were sitting
unread in the runner's /tmp, discarded when the job ended. See
docs/claude-agent-pilot-etapa4.md, section 5.4.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def render_summary(phase: str, summary: str, next_action: str, no_changes_needed: bool, reason: str) -> str:
    lines = [
        f"## Author result ({phase})",
        "",
        summary or "(no summary provided)",
        "",
        f"**Next action:** {next_action or '(no next action provided)'}",
        "",
    ]
    if no_changes_needed:
        lines.extend([
            "**No changes needed.** The author verified this phase's requirements are already "
            "satisfied and wrote nothing. This still goes to independent review below.",
            "",
            f"Reason given: {reason or '(no reason provided)'}",
            "",
        ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author-result", required=True, help="Path to author-result.json")
    parser.add_argument("--phase", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.author_result).read_text(encoding="utf-8"))
    text = render_summary(
        args.phase,
        data.get("summary", ""),
        data.get("next_action", ""),
        data.get("no_changes_needed", False),
        data.get("reason", ""),
    )

    # Always print to stdout too, so it's visible in the plain job log even
    # if GITHUB_STEP_SUMMARY isn't set (e.g. a local dry run outside Actions).
    print(text)

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
