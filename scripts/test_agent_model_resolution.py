#!/usr/bin/env python3
"""Behavioral regressions for per-agent model tier resolution."""

from __future__ import annotations

from agent_model_resolution import (
    AGENT_CATALOG,
    STRUCTURAL_AGENTS,
    resolve_effective_models,
    structural_warnings,
)


def default_config(**overrides) -> dict:
    config = {"version": 1, "reasoning_tier": "recommended", "model_overrides": {}}
    config.update(overrides)
    return config


def test_recommended_tier_matches_catalog_with_no_warnings() -> None:
    resolved = resolve_effective_models(default_config())
    for agent_id, spec in AGENT_CATALOG.items():
        assert resolved[agent_id].effective_tier == spec.recommended_tier
        assert resolved[agent_id].source == "recommended"
        assert resolved[agent_id].warning is None
    assert structural_warnings(resolved) == []


def test_economy_dial_shifts_every_agent_down_one_tier() -> None:
    resolved = resolve_effective_models(default_config(reasoning_tier="economy"))
    assert resolved["curriculum_architect"].effective_tier == "sonnet"
    assert resolved["content_author"].effective_tier == "haiku"
    # Already at the floor: cannot go below haiku.
    assert resolved["bootstrap"].effective_tier == "haiku"


def test_maximum_dial_shifts_every_agent_up_one_tier() -> None:
    resolved = resolve_effective_models(default_config(reasoning_tier="maximum"))
    assert resolved["bootstrap"].effective_tier == "sonnet"
    assert resolved["diagnostic"].effective_tier == "opus"
    # Already at the ceiling: cannot go above opus.
    assert resolved["curriculum_architect"].effective_tier == "opus"


def test_economy_dial_warns_for_structural_agents_only() -> None:
    resolved = resolve_effective_models(default_config(reasoning_tier="economy"))
    warned_ids = {agent_id for agent_id, agent in resolved.items() if agent.warning}
    assert warned_ids == STRUCTURAL_AGENTS
    assert "publish" not in warned_ids


def test_explicit_override_wins_over_dial() -> None:
    resolved = resolve_effective_models(
        default_config(reasoning_tier="maximum", model_overrides={"publish": "haiku"})
    )
    assert resolved["publish"].effective_tier == "haiku"
    assert resolved["publish"].source == "override"
    # Everything else still follows the dial.
    assert resolved["diagnostic"].effective_tier == "opus"


def test_structural_override_below_recommended_produces_warning() -> None:
    resolved = resolve_effective_models(
        default_config(model_overrides={"content_author": "haiku"})
    )
    agent = resolved["content_author"]
    assert agent.effective_tier == "haiku"
    assert agent.source == "override"
    assert agent.warning is not None
    assert "content_author" in agent.warning


def test_mechanical_override_below_recommended_has_no_warning() -> None:
    # diagnostic is not in STRUCTURAL_AGENTS, so overriding it below its
    # recommended tier (sonnet) produces no warning, unlike a structural agent.
    resolved = resolve_effective_models(default_config(model_overrides={"diagnostic": "haiku"}))
    agent = resolved["diagnostic"]
    assert agent.effective_tier == "haiku"
    assert agent.warning is None


def test_structural_override_above_recommended_has_no_warning() -> None:
    resolved = resolve_effective_models(default_config(model_overrides={"content_author": "opus"}))
    agent = resolved["content_author"]
    assert agent.effective_tier == "opus"
    assert agent.warning is None


def test_unknown_override_tier_is_rejected() -> None:
    try:
        resolve_effective_models(default_config(model_overrides={"publish": "gpt-5"}))
    except ValueError as error:
        assert "publish" in str(error)
    else:
        raise AssertionError("expected ValueError for an unknown model tier override")


def test_every_catalog_agent_has_a_resolved_entry() -> None:
    resolved = resolve_effective_models(default_config())
    assert set(resolved) == set(AGENT_CATALOG)


def main() -> None:
    tests = [
        test_recommended_tier_matches_catalog_with_no_warnings,
        test_economy_dial_shifts_every_agent_down_one_tier,
        test_maximum_dial_shifts_every_agent_up_one_tier,
        test_economy_dial_warns_for_structural_agents_only,
        test_explicit_override_wins_over_dial,
        test_structural_override_below_recommended_produces_warning,
        test_mechanical_override_below_recommended_has_no_warning,
        test_structural_override_above_recommended_has_no_warning,
        test_unknown_override_tier_is_rejected,
        test_every_catalog_agent_has_a_resolved_entry,
    ]
    for test in tests:
        test()
    print(f"Agent model resolution regressions passed ({len(tests)} cases).")


if __name__ == "__main__":
    main()
