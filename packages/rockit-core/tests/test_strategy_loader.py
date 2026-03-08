"""Tests for strategy loader, registry, and all strategy imports."""

import os
import tempfile

import yaml
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.loader import (
    _CONFIG_KEY_TO_MODULE,
    CORE_STRATEGIES,
    RESEARCH_STRATEGIES,
    get_all_strategy_classes,
    get_strategy_class,
    load_strategies_from_config,
)

# --- Registry tests ---


def test_registry_loads_all_strategies():
    classes = get_all_strategy_classes()
    assert len(classes) == 18


def test_registry_keys_match_config_keys():
    classes = get_all_strategy_classes()
    expected = set(CORE_STRATEGIES + RESEARCH_STRATEGIES)
    assert set(classes.keys()) == expected


def test_all_core_strategies_in_registry():
    classes = get_all_strategy_classes()
    for key in CORE_STRATEGIES:
        assert key in classes, f"Core strategy '{key}' missing from registry"


def test_all_research_strategies_in_registry():
    classes = get_all_strategy_classes()
    for key in RESEARCH_STRATEGIES:
        assert key in classes, f"Research strategy '{key}' missing from registry"


def test_get_strategy_class_valid():
    cls = get_strategy_class("trend_bull")
    assert cls is not None
    assert issubclass(cls, StrategyBase)


def test_get_strategy_class_invalid():
    cls = get_strategy_class("nonexistent_strategy")
    assert cls is None


# --- Instantiation tests ---


def test_all_strategies_instantiate():
    """Every strategy class can be instantiated without errors."""
    classes = get_all_strategy_classes()
    for key, cls in classes.items():
        instance = cls()
        assert isinstance(instance, StrategyBase), f"{key}: not a StrategyBase"
        assert isinstance(instance.name, str), f"{key}: name is not str"
        assert len(instance.name) > 0, f"{key}: name is empty"


def test_all_strategies_have_applicable_day_types():
    """Every strategy declares its applicable day types."""
    classes = get_all_strategy_classes()
    for key, cls in classes.items():
        instance = cls()
        day_types = instance.applicable_day_types
        assert isinstance(day_types, list), f"{key}: applicable_day_types is not a list"


def test_all_strategies_have_on_bar():
    """Every strategy implements on_bar."""
    classes = get_all_strategy_classes()
    for key, cls in classes.items():
        assert hasattr(cls, 'on_bar'), f"{key}: missing on_bar"
        assert callable(getattr(cls, 'on_bar')), f"{key}: on_bar not callable"


def test_all_strategies_have_on_session_start():
    """Every strategy implements on_session_start."""
    classes = get_all_strategy_classes()
    for key, cls in classes.items():
        assert hasattr(cls, 'on_session_start'), f"{key}: missing on_session_start"


# --- Strategy name uniqueness ---


def test_strategy_names_are_unique():
    """No two strategies share the same display name."""
    classes = get_all_strategy_classes()
    names = set()
    for key, cls in classes.items():
        instance = cls()
        name = instance.name
        assert name not in names, f"Duplicate strategy name: '{name}'"
        names.add(name)


# --- YAML config loading ---


def _repo_root():
    """Find repo root by walking up from this file."""
    d = os.path.abspath(__file__)
    for _ in range(10):
        d = os.path.dirname(d)
        if os.path.exists(os.path.join(d, "pyproject.toml")) and os.path.exists(os.path.join(d, "configs")):
            return d
    return None


def _write_yaml_config(config: dict) -> str:
    """Write config to a temp YAML file and return its path (caller must clean up)."""
    fd, path = tempfile.mkstemp(suffix='.yaml')
    with os.fdopen(fd, 'w') as f:
        yaml.dump(config, f)
    return path


def test_load_core_strategies_from_config():
    """Load from the real strategies.yaml — should get enabled strategies."""
    root = _repo_root()
    assert root is not None, "Could not find repo root"
    config_path = os.path.join(root, "configs", "strategies.yaml")
    assert os.path.exists(config_path), f"strategies.yaml not found at {config_path}"

    strategies = load_strategies_from_config(config_path)
    assert len(strategies) == 5  # 5 core strategies enabled, rest disabled

    names = {s.name for s in strategies}
    assert "80P Rule" in names
    assert "B-Day" in names
    assert "Opening Range Rev" in names
    assert "20P IB Extension" in names


def test_load_all_strategies_from_custom_config():
    """When all strategies are enabled, all 18 load."""
    config = {
        'core_strategies': {key: {'enabled': True} for key in CORE_STRATEGIES},
        'research_strategies': {key: {'enabled': True} for key in RESEARCH_STRATEGIES},
    }
    path = _write_yaml_config(config)
    try:
        strategies = load_strategies_from_config(path)
        assert len(strategies) == 18
    finally:
        os.unlink(path)


def test_load_no_strategies_when_all_disabled():
    """When all strategies are disabled, empty list returned."""
    config = {
        'core_strategies': {key: {'enabled': False} for key in CORE_STRATEGIES},
        'research_strategies': {key: {'enabled': False} for key in RESEARCH_STRATEGIES},
    }
    path = _write_yaml_config(config)
    try:
        strategies = load_strategies_from_config(path)
        assert len(strategies) == 0
    finally:
        os.unlink(path)


def test_load_strategies_ignores_unknown_keys():
    """Unknown strategy keys in YAML are silently ignored."""
    config = {
        'core_strategies': {
            'trend_bull': {'enabled': True},
            'unknown_strategy': {'enabled': True},
        },
    }
    path = _write_yaml_config(config)
    try:
        strategies = load_strategies_from_config(path)
        assert len(strategies) == 1
    finally:
        os.unlink(path)


# --- Config key mapping completeness ---


def test_config_key_mapping_covers_all_groups():
    """Every strategy in CORE + RESEARCH lists has a module mapping."""
    all_keys = set(CORE_STRATEGIES + RESEARCH_STRATEGIES)
    mapped_keys = set(_CONFIG_KEY_TO_MODULE.keys())
    assert all_keys == mapped_keys
