"""
Market Structure Module Registry.

Configurable registry of market observation modules that the orchestrator runs.
Each module detects market conditions (levels, sweeps, acceptance, extensions)
without generating trade signals. To add a new module: add an entry here +
create the module file.
"""

import importlib

MARKET_MODULES = [
    {
        "name": "or_analysis",
        "module": "rockit_core.deterministic.modules.or_reversal",
        "function": "get_or_analysis",
        "description": "Opening Range levels, sweeps, drive type",
        "enabled": True,
        "args_type": "or",
    },
    {
        "name": "prior_va_analysis",
        "module": "rockit_core.deterministic.modules.globex_va_analysis",
        "function": "get_prior_va_analysis",
        "description": "Prior session VA, gap status, acceptance models",
        "enabled": True,
        "args_type": "globex",
    },
    {
        "name": "ib_extension",
        "module": "rockit_core.deterministic.modules.twenty_percent_rule",
        "function": "get_ib_extension_analysis",
        "description": "IB extension tracking, consecutive closes",
        "enabled": True,
        "args_type": "twenty_p",
    },
    {
        "name": "balance_type",
        "module": "rockit_core.deterministic.modules.balance_classification",
        "function": "get_balance_classification",
        "description": "Balance day P/b/neutral classification",
        "enabled": True,
        "args_type": "standard",
    },
    {
        "name": "range_classification",
        "module": "rockit_core.deterministic.modules.mean_reversion_engine",
        "function": "get_range_analysis",
        "description": "IB range tight/normal/wide + rejection tests",
        "enabled": True,
        "args_type": "standard",
    },
    {
        "name": "edge_zone",
        "module": "rockit_core.deterministic.modules.edge_fade",
        "function": "get_edge_zone_analysis",
        "description": "Edge zone detection, IB expansion, order flow",
        "enabled": True,
        "args_type": "edge",
    },
    {
        "name": "va_poke",
        "module": "rockit_core.deterministic.modules.va_edge_fade",
        "function": "get_va_poke_analysis",
        "description": "VA edge poke detection, rejection patterns",
        "enabled": True,
        "args_type": "va_poke",
    },
]


def load_market_structure(registry, df_extended, df_current, intraday_data,
                          config, ib_data, premarket_data):
    """
    Dynamically load and run all enabled market structure modules.

    Args:
        registry: List of module entries from MARKET_MODULES
        df_extended: Full historical DataFrame
        df_current: Current session DataFrame
        intraday_data: Dict with ib, volume_profile, etc.
        config: Orchestrator config dict
        ib_data: IB location output
        premarket_data: Premarket output

    Returns:
        dict: {module_name: module_output} for all enabled modules
    """
    results = {}
    current_time = config['current_time']
    session_date = config['session_date']

    # Get prior VA data (needed by va_poke module)
    gva = None

    for entry in registry:
        if not entry["enabled"]:
            continue

        try:
            mod = importlib.import_module(entry["module"])
            func = getattr(mod, entry["function"])

            args_type = entry.get("args_type", "standard")

            if args_type == "or":
                intraday_with_premarket = dict(intraday_data)
                intraday_with_premarket['premarket'] = premarket_data
                result = func(df_current, current_time, intraday_with_premarket)
            elif args_type == "globex":
                result = func(df_extended, df_current, current_time,
                              session_date=session_date,
                              tpo_profile=intraday_data.get('tpo_profile'))
                gva = result  # Cache for va_poke module
            elif args_type == "twenty_p":
                result = func(
                    df_current, current_time,
                    atr14=ib_data.get('atr14'),
                    ib_high=ib_data.get('ib_high'),
                    ib_low=ib_data.get('ib_low'),
                    ib_range=ib_data.get('ib_range'),
                    volume_profile=intraday_data.get('volume_profile'),
                    tpo_profile=intraday_data.get('tpo_profile'),
                )
            elif args_type == "edge":
                ib_history_5days = [ib_data.get('ib_range', 0)] if ib_data else [0]
                result = func(df_current, intraday_data, current_time, ib_history_5days)
            elif args_type == "va_poke":
                if gva is None:
                    gva = {}
                result = func(
                    df_current, current_time,
                    previous_session_vah=gva.get('previous_session_vah'),
                    previous_session_val=gva.get('previous_session_val'),
                    atr14=ib_data.get('atr14'),
                )
            else:  # standard: (df, intraday_data, time)
                result = func(df_current, intraday_data, current_time)

            results[entry["name"]] = result

        except Exception as e:
            results[entry["name"]] = {"error": str(e), "status": "failed"}

    return results
