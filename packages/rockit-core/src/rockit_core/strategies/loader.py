"""
Strategy loader — loads strategies from YAML config.

Usage:
    strategies = load_strategies_from_config("configs/strategies.yaml")
"""

from __future__ import annotations

from pathlib import Path

import yaml

from rockit_core.strategies.base import StrategyBase

# Registry mapping config key (snake_case) to strategy class.
# Populated lazily to avoid circular imports.
_STRATEGY_REGISTRY: dict[str, type[StrategyBase]] = {}


# Explicit mapping from YAML config keys to (module, class_name).
# This avoids fragile fuzzy matching and documents the exact mapping.
_CONFIG_KEY_TO_MODULE: dict[str, tuple[str, str]] = {
    "trend_bull": ("rockit_core.strategies.trend_bull", "TrendDayBull"),
    "trend_bear": ("rockit_core.strategies.trend_bear", "TrendDayBear"),
    "super_trend_bull": ("rockit_core.strategies.super_trend_bull", "SuperTrendBull"),
    "super_trend_bear": ("rockit_core.strategies.super_trend_bear", "SuperTrendBear"),
    "p_day": ("rockit_core.strategies.p_day", "PDayStrategy"),
    "b_day": ("rockit_core.strategies.b_day", "BDayStrategy"),
    "eighty_percent_rule": ("rockit_core.strategies.eighty_percent_rule", "EightyPercentRule"),
    "mean_reversion_vwap": ("rockit_core.strategies.mean_reversion_vwap", "MeanReversionVWAP"),
    "orb_enhanced": ("rockit_core.strategies.orb_enhanced", "ORBEnhanced"),
    "neutral_day": ("rockit_core.strategies.neutral_day", "NeutralDayStrategy"),
    "pm_morph": ("rockit_core.strategies.pm_morph", "PMMorphStrategy"),
    "morph_to_trend": ("rockit_core.strategies.morph_to_trend", "MorphToTrendStrategy"),
    "orb_vwap_breakout": ("rockit_core.strategies.orb_vwap_breakout", "ORBVwapBreakout"),
    "ema_trend_follow": ("rockit_core.strategies.ema_trend_follow", "EMATrendFollow"),
    "liquidity_sweep": ("rockit_core.strategies.liquidity_sweep", "LiquiditySweep"),
    "or_reversal": ("rockit_core.strategies.or_reversal", "OpeningRangeReversal"),
    "or_acceptance": ("rockit_core.strategies.or_acceptance", "ORAcceptanceStrategy"),
    "twenty_percent_rule": ("rockit_core.strategies.twenty_percent_rule", "TwentyPercentRule"),
    "nwog_gap_fill": ("rockit_core.strategies.nwog_gap_fill", "NWOGGapFill"),
    "pdh_pdl_reaction": ("rockit_core.strategies.pdh_pdl_reaction", "PDHPDLReaction"),
    "ndog_gap_fill": ("rockit_core.strategies.ndog_gap_fill", "NDOGGapFill"),
    "single_print_gap_fill": ("rockit_core.strategies.single_print_gap_fill", "SinglePrintGapFill"),
    "poor_highlow_repair": ("rockit_core.strategies.poor_highlow_repair", "PoorHighLowRepair"),
    "cvd_divergence": ("rockit_core.strategies.cvd_divergence", "CVDDivergence"),
    "rth_gap_fill": ("rockit_core.strategies.rth_gap_fill", "RTHGapFill"),
    "double_distribution": ("rockit_core.strategies.double_distribution", "DoubleDistributionStrategy"),
    "va_edge_fade": ("rockit_core.strategies.va_edge_fade", "VAEdgeFade"),
    "ib_edge_fade": ("rockit_core.strategies.ib_edge_fade", "IBEdgeFade"),
    "ib_retracement": ("rockit_core.strategies.ib_retracement", "IBRetracement"),
}


def _ensure_registry():
    """Populate the strategy registry if not already done."""
    if _STRATEGY_REGISTRY:
        return

    import importlib

    for config_key, (module_path, class_name) in _CONFIG_KEY_TO_MODULE.items():
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        _STRATEGY_REGISTRY[config_key] = cls


def get_all_strategy_classes() -> dict[str, type[StrategyBase]]:
    """Return a dict of config_key -> strategy_class."""
    _ensure_registry()
    return dict(_STRATEGY_REGISTRY)


def get_strategy_class(config_key: str) -> type[StrategyBase] | None:
    """Return strategy class for a given config key, or None."""
    _ensure_registry()
    return _STRATEGY_REGISTRY.get(config_key)


# Strategy groupings
CORE_STRATEGIES = [
    "trend_bull", "trend_bear",
    "super_trend_bull", "super_trend_bear",
    "p_day", "b_day",
    "eighty_percent_rule", "mean_reversion_vwap",
    "orb_enhanced",
    "or_reversal", "or_acceptance", "twenty_percent_rule",
]

RESEARCH_STRATEGIES = [
    "neutral_day", "pm_morph", "morph_to_trend",
    "orb_vwap_breakout", "ema_trend_follow", "liquidity_sweep",
    "nwog_gap_fill", "pdh_pdl_reaction",
    "ndog_gap_fill", "single_print_gap_fill", "poor_highlow_repair",
    "cvd_divergence", "rth_gap_fill", "double_distribution",
    "va_edge_fade", "ib_edge_fade", "ib_retracement",
]


def load_strategies_from_config(config_path: str | Path) -> list[StrategyBase]:
    """Load enabled strategies from a YAML config file.

    Args:
        config_path: Path to strategies.yaml

    Returns:
        List of instantiated strategy objects for enabled strategies.
    """
    _ensure_registry()

    config_path = Path(config_path)
    with open(config_path) as f:
        config = yaml.safe_load(f)

    strategies = []

    for section in ['core_strategies', 'research_strategies']:
        section_config = config.get(section, {})
        for name, settings in section_config.items():
            if not settings.get('enabled', False):
                continue

            cls = _STRATEGY_REGISTRY.get(name)
            if cls is not None:
                strategies.append(cls())

    return strategies
