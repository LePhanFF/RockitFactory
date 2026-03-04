"""Smoke tests: every migrated module imports without errors."""

import importlib

import pytest

# All rockit_core subpackages and modules that must import cleanly.
IMPORTABLE_MODULES = [
    # Top-level
    "rockit_core",
    # Strategies
    "rockit_core.strategies",
    "rockit_core.strategies.base",
    "rockit_core.strategies.signal",
    "rockit_core.strategies.day_type",
    "rockit_core.strategies.day_confidence",
    "rockit_core.strategies.loader",
    "rockit_core.strategies.trend_bull",
    "rockit_core.strategies.trend_bear",
    "rockit_core.strategies.super_trend_bull",
    "rockit_core.strategies.super_trend_bear",
    "rockit_core.strategies.p_day",
    "rockit_core.strategies.b_day",
    "rockit_core.strategies.eighty_percent_rule",
    "rockit_core.strategies.mean_reversion_vwap",
    "rockit_core.strategies.orb_enhanced",
    "rockit_core.strategies.neutral_day",
    "rockit_core.strategies.pm_morph",
    "rockit_core.strategies.morph_to_trend",
    "rockit_core.strategies.orb_vwap_breakout",
    "rockit_core.strategies.ema_trend_follow",
    "rockit_core.strategies.liquidity_sweep",
    # Engine
    "rockit_core.engine",
    "rockit_core.engine.backtest",
    "rockit_core.engine.trade",
    "rockit_core.engine.execution",
    "rockit_core.engine.position",
    "rockit_core.engine.equity",
    # Filters
    "rockit_core.filters",
    "rockit_core.filters.base",
    "rockit_core.filters.composite",
    "rockit_core.filters.time_filter",
    "rockit_core.filters.trend_filter",
    "rockit_core.filters.volatility_filter",
    "rockit_core.filters.order_flow_filter",
    "rockit_core.filters.regime_filter",
    # Indicators
    "rockit_core.indicators",
    "rockit_core.indicators.technical",
    "rockit_core.indicators.ib_width",
    "rockit_core.indicators.value_area",
    "rockit_core.indicators.smt_divergence",
    "rockit_core.indicators.ict_models",
    # Profile
    "rockit_core.profile",
    "rockit_core.profile.tpo_profile",
    "rockit_core.profile.volume_profile",
    "rockit_core.profile.dpoc_migration",
    "rockit_core.profile.ib_analysis",
    "rockit_core.profile.wick_parade",
    "rockit_core.profile.confluences",
    # Data
    "rockit_core.data",
    "rockit_core.data.loader",
    "rockit_core.data.session",
    "rockit_core.data.features",
    # Config
    "rockit_core.config",
    "rockit_core.config.constants",
    "rockit_core.config.instruments",
    # Reporting
    "rockit_core.reporting",
    "rockit_core.reporting.metrics",
    "rockit_core.reporting.trade_log",
    "rockit_core.reporting.day_analyzer",
    "rockit_core.reporting.comparison",
    # Metrics
    "rockit_core.metrics",
    "rockit_core.metrics.events",
    "rockit_core.metrics.collector",
    # Models
    "rockit_core.models",
    "rockit_core.models.signals",
    "rockit_core.models.base",
    "rockit_core.models.entry_models",
    "rockit_core.models.stop_models",
    "rockit_core.models.target_models",
    "rockit_core.models.registry",
    # Deterministic
    "rockit_core.deterministic",
    "rockit_core.deterministic.orchestrator",
]


@pytest.mark.parametrize("module_path", IMPORTABLE_MODULES)
def test_import(module_path):
    """Each module imports without errors."""
    importlib.import_module(module_path)
