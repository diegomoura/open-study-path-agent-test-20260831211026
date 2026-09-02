#!/usr/bin/env python3
"""Regressions for scripts/build_agent_prompt.py's current-time grounding.

Deliberately narrow: build_agent_prompt.py assembles prompts almost
entirely from real instructions/*.md files (by design, see the module's
own docstring), so a broad test suite here would just re-read those files.
This covers the one thing that is actually code logic worth a regression
test: real dispatch finding (Etapa 12/14 validation session) that no
phase told the model the real current date/time, so every model-authored
timestamp field was a guess.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from build_agent_prompt import build_author_prompts, build_reviewer_prompts, current_utc_timestamp

TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_current_utc_timestamp_format_and_recency() -> None:
    value = current_utc_timestamp()
    assert TIMESTAMP_PATTERN.match(value), value
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    delta = abs((datetime.now(timezone.utc) - parsed).total_seconds())
    assert delta < 5, f"timestamp not close to now: {value}"


def test_build_author_prompts_includes_real_current_time() -> None:
    _, user_prompt = build_author_prompts("bootstrap_instance", "owner/repo", "")
    assert "Current UTC date and time:" in user_prompt
    # The instructive sentence must actually tell the model to use this
    # value rather than guessing -- the bug this guards against wasn't a
    # missing feature, it was a genuinely absent fact plus no instruction
    # to avoid inventing one.
    assert "Never guess or copy an example date" in user_prompt


def test_build_reviewer_prompts_includes_real_current_time() -> None:
    _, user_prompt = build_reviewer_prompts("bootstrap_instance", "owner/repo", "HEAD", "author summary")
    assert "Current UTC date and time:" in user_prompt
    assert "Never guess or copy an example date" in user_prompt


def main() -> None:
    tests = [
        test_current_utc_timestamp_format_and_recency,
        test_build_author_prompts_includes_real_current_time,
        test_build_reviewer_prompts_includes_real_current_time,
    ]
    for test in tests:
        test()
    print(f"build_agent_prompt regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
