"""
Filter pipeline builder — constructs CompositeFilter from YAML config.

No hardcoded rules. Adding new rules = edit YAML, zero code changes.
"""

from pathlib import Path
from typing import Optional

import yaml

from rockit_core.filters.anti_chase_filter import AntiChaseFilter
from rockit_core.filters.bias_filter import BiasAlignmentFilter
from rockit_core.filters.composite import CompositeFilter
from rockit_core.filters.day_type_gate_filter import DayTypeGateFilter


def build_filter_pipeline(
    config_path: str = "configs/filters.yaml",
) -> Optional[CompositeFilter]:
    """Build CompositeFilter from YAML config. No hardcoded rules.

    Args:
        config_path: Path to filter pipeline YAML config.

    Returns:
        CompositeFilter if any filters enabled, None otherwise.
    """
    path = Path(config_path)
    if not path.exists():
        return None

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    pipeline_cfg = config.get("pipeline", {})
    filters = []

    # Bias alignment
    bias_cfg = pipeline_cfg.get("bias_alignment", {})
    if bias_cfg.get("enabled"):
        filters.append(BiasAlignmentFilter(
            neutral_passes=bias_cfg.get("neutral_passes", True),
        ))

    # Day type gate
    dt_cfg = pipeline_cfg.get("day_type_gate", {})
    if dt_cfg.get("enabled"):
        filters.append(DayTypeGateFilter(
            rules=dt_cfg.get("rules", []),
        ))

    # Anti-chase
    ac_cfg = pipeline_cfg.get("anti_chase", {})
    if ac_cfg.get("enabled"):
        filters.append(AntiChaseFilter(
            rules=ac_cfg.get("rules", []),
        ))

    # Agent evaluation
    agent_cfg = pipeline_cfg.get("agent_evaluation", {})
    if agent_cfg.get("enabled"):
        from rockit_core.agents.agent_filter import AgentFilter
        from rockit_core.agents.orchestrator import DeterministicOrchestrator
        from rockit_core.agents.pipeline import AgentPipeline

        orchestrator = DeterministicOrchestrator(
            take_threshold=agent_cfg.get("take_threshold", 0.3),
            skip_threshold=agent_cfg.get("skip_threshold", 0.1),
        )
        pipeline = AgentPipeline(orchestrator=orchestrator)
        filters.append(AgentFilter(pipeline=pipeline))

    return CompositeFilter(filters) if filters else None
