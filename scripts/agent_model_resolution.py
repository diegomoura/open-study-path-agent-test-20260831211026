#!/usr/bin/env python3
"""Resolve which Claude model tier each multi-agent role should use.

This module is pure logic: it never reads a file and never calls an API.
It exists so the model-selection rules can be unit tested in isolation,
before any agent workflow actually spends a token (see docs/agent-model-configuration.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# Low -> high reasoning capability. Values are internal tier names, not API model ids.
TIER_ORDER: tuple[str, ...] = ("haiku", "sonnet", "opus")

# Maps an internal tier name to the Claude API model id that should be used for it.
# Verify against https://docs.claude.com/en/docs/about-claude/models before wiring
# real API calls (stage 2+) -- these ids are current as of this writing but Anthropic
# ships new model versions over time.
MODEL_CATALOG: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-4-8",
}

REASONING_TIER_SHIFT: dict[str, int] = {"economy": -1, "recommended": 0, "maximum": 1}

# Agents flagged here make (or check) a structural decision -- the roadmap graph,
# a full lesson's teaching content, or a mastery judgment. Configuring one of these
# below its recommended tier gets a non-blocking warning: it is a real cost/quality
# trade-off, not a silent default.
STRUCTURAL_AGENTS: frozenset[str] = frozenset(
    {
        "curriculum_architect",
        "curriculum_reviewer",
        "content_author",
        "content_reviewer",
        "evaluate",
    }
)


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    phase: str
    role: str
    recommended_tier: str
    structural: bool


@dataclass(frozen=True)
class ResolvedAgent:
    agent_id: str
    phase: str
    role: str
    recommended_tier: str
    effective_tier: str
    model: str
    source: str  # "recommended", "dial", or "override"
    warning: str | None


# One row per row of the "Mapa de agentes por fase" table in the work proposal.
AGENT_CATALOG: dict[str, AgentSpec] = {
    "bootstrap": AgentSpec("bootstrap", "bootstrap_instance", "author", "haiku", False),
    "configure_intake": AgentSpec("configure_intake", "configure_intake", "author", "haiku", False),
    "intake_resolution": AgentSpec("intake_resolution", "intake", "author", "haiku", False),
    "diagnostic": AgentSpec("diagnostic", "diagnostic", "author", "sonnet", False),
    "curriculum_architect": AgentSpec("curriculum_architect", "generate", "author", "opus", True),
    "curriculum_reviewer": AgentSpec("curriculum_reviewer", "generate", "reviewer", "opus", True),
    "content_author": AgentSpec("content_author", "generate|evaluate", "author", "sonnet", True),
    "content_reviewer": AgentSpec("content_reviewer", "generate|evaluate", "reviewer", "sonnet", True),
    "publish": AgentSpec("publish", "publish", "author", "haiku", False),
    "integration_preflight": AgentSpec("integration_preflight", "publish", "reviewer", "haiku", False),
    "evaluate": AgentSpec("evaluate", "evaluate", "author", "sonnet", True),
    # Etapa 6a (docs/claude-agent-pilot-etapa6-design.md, section 3.1): `track`
    # never had a row here or in templates/agent-models.yml -- a real gap in
    # the original model-tier design, not just harness wiring. Haiku,
    # non-structural: in the pilot's restricted scope (github_issues backend
    # only), instructions/50-track-progress.md is state synchronization
    # against well-defined transition rules (mastery only from a verified
    # evaluation, external activity never sufficient alone), same class as
    # publish/integration_preflight, not curriculum_architect/evaluate.
    "track": AgentSpec("track", "track", "author", "haiku", False),
    "replan": AgentSpec("replan", "replan", "author", "sonnet", False),
}


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _shift_tier(tier: str, steps: int) -> str:
    index = TIER_ORDER.index(tier)
    index = max(0, min(len(TIER_ORDER) - 1, index + steps))
    return TIER_ORDER[index]


def resolve_effective_models(config: Mapping[str, Any]) -> dict[str, ResolvedAgent]:
    """Resolve the effective (tier, model) for every known agent.

    `config` is the parsed content of .open-study-path/models.yml (or
    templates/agent-models.yml in template mode). Unknown keys are ignored here;
    schema validation (scripts/validate_model_config.py) is responsible for
    rejecting a malformed document before this function ever sees it.
    """
    dial = _text(config.get("reasoning_tier")) or "recommended"
    if dial not in REASONING_TIER_SHIFT:
        dial = "recommended"
    shift = REASONING_TIER_SHIFT[dial]

    overrides = _mapping(config.get("model_overrides"))

    resolved: dict[str, ResolvedAgent] = {}
    for agent_id, spec in AGENT_CATALOG.items():
        override_tier = _text(overrides.get(agent_id)) or None

        if override_tier:
            if override_tier not in TIER_ORDER:
                raise ValueError(f"unknown model tier override for {agent_id}: {override_tier}")
            effective_tier = override_tier
            source = "override"
        elif shift:
            effective_tier = _shift_tier(spec.recommended_tier, shift)
            source = "dial"
        else:
            effective_tier = spec.recommended_tier
            source = "recommended"

        warning = None
        if spec.structural and TIER_ORDER.index(effective_tier) < TIER_ORDER.index(spec.recommended_tier):
            warning = (
                f"{agent_id} is configured for '{effective_tier}', below its recommended tier "
                f"('{spec.recommended_tier}') for a structural decision. Generated or reviewed "
                "content is likely to be less thorough than the default."
            )

        resolved[agent_id] = ResolvedAgent(
            agent_id=agent_id,
            phase=spec.phase,
            role=spec.role,
            recommended_tier=spec.recommended_tier,
            effective_tier=effective_tier,
            model=MODEL_CATALOG[effective_tier],
            source=source,
            warning=warning,
        )

    return resolved


def structural_warnings(resolved: Mapping[str, ResolvedAgent]) -> list[str]:
    return [agent.warning for agent in resolved.values() if agent.warning]
