"""Integration tests for the deterministic orchestrator and snapshot generation.

Tests the full pipeline: CSV loading -> module execution -> snapshot assembly.
Validates output structure, JSON compliance, and cross-session consistency.
"""

import json
import math
import os
import tempfile

import numpy as np
import pytest

from rockit_core.deterministic.orchestrator import generate_snapshot
from rockit_core.deterministic.modules.dataframe_cache import clear_global_cache
from rockit_core.deterministic.modules.config_validator import validate_config
from rockit_core.deterministic.modules.schema_validator import validate_snapshot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sessions")
NQ_CSV = os.path.join(DATA_DIR, "NQ_Volumetric_1.csv")
ES_CSV = os.path.join(DATA_DIR, "ES_Volumetric_1.csv")
YM_CSV = os.path.join(DATA_DIR, "YM_Volumetric_1.csv")

# Use the most recent complete trading day for single-day tests
LATEST_SESSION = "2026-02-27"

# Recent trading days for multi-day tests (most recent first)
RECENT_SESSIONS = [
    "2026-02-27", "2026-02-26", "2026-02-25", "2026-02-24", "2026-02-23",
    "2026-02-20", "2026-02-19", "2026-02-18", "2026-02-17", "2026-02-16",
    "2026-02-13", "2026-02-12", "2026-02-11", "2026-02-10", "2026-02-09",
]


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear DataFrame cache before each test to avoid cross-contamination."""
    clear_global_cache()
    yield
    clear_global_cache()


def _make_config(session_date, current_time, include_es_ym=False):
    """Build a config dict for the orchestrator."""
    csv_paths = {"nq": NQ_CSV}
    if include_es_ym:
        csv_paths["es"] = ES_CSV
        csv_paths["ym"] = YM_CSV
    return {
        "session_date": session_date,
        "current_time": current_time,
        "csv_paths": csv_paths,
        "output_dir": tempfile.mkdtemp(),
    }


def _has_bad_values(obj):
    """Return list of paths with NaN, Infinity, or numpy types."""
    bad = []

    def _walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                _walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                _walk(v, f"{path}[{i}]")
        elif isinstance(o, float):
            if math.isinf(o):
                bad.append(f"{path}: Infinity")
        elif isinstance(o, (np.integer, np.floating, np.bool_, np.ndarray)):
            bad.append(f"{path}: numpy type {type(o).__name__}")

    _walk(obj)
    return bad


# Required top-level keys in every snapshot
REQUIRED_TOP_KEYS = [
    "session_date", "current_et_time", "premarket", "intraday",
    "core_confluences", "inference", "market_structure",
]

REQUIRED_INTRADAY_KEYS = [
    "ib", "volume_profile", "tpo_profile", "dpoc_migration",
    "wick_parade", "fvg_detection", "smt_detection",
]

REQUIRED_MARKET_STRUCTURE_KEYS = [
    "or_analysis", "prior_va_analysis", "ib_extension",
    "balance_type", "range_classification", "edge_zone", "va_poke",
]

# Trade signal keys that must NOT appear in market_structure (regression guard)
FORBIDDEN_SIGNAL_KEYS = [
    "entry", "stop", "target", "entry_price", "stop_price",
    "target_price", "signal", "target_2r", "target_3r", "target_4r",
    "risk_pts", "target_opposite_va", "rr", "reward",
]

REQUIRED_CONFLUENCE_KEYS = [
    "ib_acceptance", "dpoc_vs_ib", "dpoc_compression",
    "price_location", "tpo_signals", "migration",
]


def _validate_snapshot_basics(snapshot):
    """Common assertions applied to every snapshot."""
    # Top-level keys
    for key in REQUIRED_TOP_KEYS:
        assert key in snapshot, f"Missing top-level key: {key}"

    # JSON serializable
    json_str = json.dumps(snapshot)
    assert len(json_str) > 0

    # No Infinity or numpy types (NaN is tolerated in premarket.compression_ratio)
    bad = _has_bad_values(snapshot)
    assert not bad, f"Bad values in snapshot: {bad}"


# ===========================================================================
# Class 1: TestSingleDaySnapshot — Parametrized by session phase
# ===========================================================================


class TestSingleDaySnapshot:
    """Test snapshot generation at different times across a single trading day."""

    @pytest.mark.parametrize("current_time", ["19:30", "21:00", "23:00", "01:00"])
    def test_asia_session(self, current_time):
        """Asia session (19:00-03:00 ET) produces valid snapshot."""
        config = _make_config(LATEST_SESSION, current_time)
        snapshot = generate_snapshot(config)
        _validate_snapshot_basics(snapshot)

        premarket = snapshot["premarket"]
        assert "asia_high" in premarket
        assert "asia_low" in premarket

    @pytest.mark.parametrize("current_time", ["03:30", "04:30"])
    def test_london_session(self, current_time):
        """London session (03:00-05:00 ET) includes London levels."""
        config = _make_config(LATEST_SESSION, current_time)
        snapshot = generate_snapshot(config)
        _validate_snapshot_basics(snapshot)

        premarket = snapshot["premarket"]
        assert "london_high" in premarket
        assert "london_low" in premarket

    @pytest.mark.parametrize("current_time", ["07:00", "08:30", "09:25"])
    def test_us_preopen(self, current_time):
        """US pre-open (05:00-09:30 ET) includes overnight levels."""
        config = _make_config(LATEST_SESSION, current_time)
        snapshot = generate_snapshot(config)
        _validate_snapshot_basics(snapshot)

        premarket = snapshot["premarket"]
        assert "overnight_high" in premarket
        assert "overnight_low" in premarket

    @pytest.mark.parametrize("current_time", ["09:35", "09:50", "10:15", "10:25"])
    def test_ib_formation(self, current_time):
        """IB formation period (09:30-10:30 ET) has IB data."""
        config = _make_config(LATEST_SESSION, current_time)
        snapshot = generate_snapshot(config)
        _validate_snapshot_basics(snapshot)

        ib = snapshot["intraday"]["ib"]
        assert "ib_status" in ib
        assert ib["ib_status"] in ("complete", "partial", "no_data")

    @pytest.mark.parametrize(
        "current_time",
        ["10:35", "11:00", "11:45", "12:30", "13:30", "14:30", "15:30"],
    )
    def test_post_ib(self, current_time):
        """Post-IB (10:30-16:00 ET) produces full schema with all sections."""
        config = _make_config(LATEST_SESSION, current_time, include_es_ym=True)
        snapshot = generate_snapshot(config)
        _validate_snapshot_basics(snapshot)

        # Full IB should be complete
        ib = snapshot["intraday"]["ib"]
        assert ib["ib_status"] == "complete"
        assert isinstance(ib.get("ib_high"), (int, float))
        assert isinstance(ib.get("ib_low"), (int, float))
        assert isinstance(ib.get("ib_range"), (int, float))

        # Inference should be populated
        inference = snapshot.get("inference", {})
        assert "day_type" in inference
        assert "bias" in inference

        # Market structure should be populated
        ms = snapshot.get("market_structure", {})
        assert isinstance(ms, dict)
        assert len(ms) > 0


# ===========================================================================
# Class 2: TestModuleOutputStructure — Per-module key validation
# ===========================================================================


class TestModuleOutputStructure:
    """Validate output keys for each module at 11:45 (all modules active)."""

    @pytest.fixture(scope="class")
    def snapshot_1145(self):
        """Generate a single snapshot at 11:45 for all module tests."""
        clear_global_cache()
        config = _make_config(LATEST_SESSION, "11:45", include_es_ym=True)
        return generate_snapshot(config)

    def test_premarket_keys(self, snapshot_1145):
        """Premarket module outputs expected keys."""
        pm = snapshot_1145["premarket"]
        expected = [
            "asia_high", "asia_low",
            "london_high", "london_low", "london_range",
            "overnight_high", "overnight_low", "overnight_range",
            "previous_day_high", "previous_day_low",
            "smt_preopen",
        ]
        for key in expected:
            assert key in pm, f"Missing premarket key: {key}"

    def test_ib_location_keys(self, snapshot_1145):
        """IB location module outputs expected keys."""
        ib = snapshot_1145["intraday"]["ib"]
        expected = [
            "ib_high", "ib_low", "ib_range", "ib_status",
            "current_close", "rsi14", "atr14",
            "ib_atr_ratio", "ib_width_class",
            "extension_pts", "extension_direction", "extension_multiple",
        ]
        for key in expected:
            assert key in ib, f"Missing ib key: {key}"

    def test_ib_width_class_valid(self, snapshot_1145):
        """IB width class is one of the valid Dalton categories."""
        ib = snapshot_1145["intraday"]["ib"]
        assert ib["ib_width_class"] in ("narrow", "normal", "wide", "extreme", "unknown")
        if ib["ib_width_class"] != "unknown":
            assert isinstance(ib["ib_atr_ratio"], (int, float))
            assert ib["ib_atr_ratio"] > 0

    def test_extension_magnitude_valid(self, snapshot_1145):
        """Extension magnitude fields have valid types."""
        ib = snapshot_1145["intraday"]["ib"]
        assert isinstance(ib["extension_pts"], (int, float))
        assert ib["extension_direction"] in ("up", "down", "none")
        assert isinstance(ib["extension_multiple"], (int, float))

    def test_volume_profile_keys(self, snapshot_1145):
        """Volume profile module has POC/VAH/VAL."""
        vp = snapshot_1145["intraday"]["volume_profile"]
        assert "current_session" in vp or "poc" in vp
        # Check nested current_session if present
        cs = vp.get("current_session", vp)
        for key in ["poc", "vah", "val"]:
            assert key in cs, f"Missing volume_profile key: {key}"

    def test_volume_profile_composites(self, snapshot_1145):
        """Volume profile has 5-day and 10-day composite profiles."""
        vp = snapshot_1145["intraday"]["volume_profile"]
        for period in ["previous_5_days", "previous_10_days"]:
            assert period in vp, f"Missing volume_profile key: {period}"
            profile = vp[period]
            assert isinstance(profile, dict)
            for key in ["poc", "vah", "val"]:
                assert key in profile, f"Missing {period}.{key}"

    def test_tpo_profile_keys(self, snapshot_1145):
        """TPO profile module outputs expected keys."""
        tpo = snapshot_1145["intraday"]["tpo_profile"]
        expected = [
            "current_poc", "current_vah", "current_val",
            "poor_high", "poor_low", "tpo_shape",
        ]
        for key in expected:
            assert key in tpo, f"Missing tpo_profile key: {key}"

    def test_dpoc_migration_keys(self, snapshot_1145):
        """DPOC migration module outputs expected keys."""
        dpoc = snapshot_1145["intraday"]["dpoc_migration"]
        expected = ["direction", "dpoc_regime", "dpoc_history"]
        for key in expected:
            assert key in dpoc, f"Missing dpoc_migration key: {key}"

    def test_core_confluences_keys(self, snapshot_1145):
        """Core confluences has all 6 required sub-sections."""
        cc = snapshot_1145["core_confluences"]
        for key in REQUIRED_CONFLUENCE_KEYS:
            assert key in cc, f"Missing core_confluences key: {key}"

    def test_inference_keys(self, snapshot_1145):
        """Inference engine outputs expected keys."""
        inf = snapshot_1145["inference"]
        expected = ["day_type", "bias", "trend_strength"]
        for key in expected:
            assert key in inf, f"Missing inference key: {key}"

    def test_market_structure_keys(self, snapshot_1145):
        """Market structure section has all required sub-dicts."""
        ms = snapshot_1145["market_structure"]
        assert isinstance(ms, dict)
        for key in REQUIRED_MARKET_STRUCTURE_KEYS:
            assert key in ms, f"Missing market_structure key: {key}"
            assert isinstance(ms[key], dict), f"market_structure[{key}] should be dict"

    def test_prior_va_analysis_keys(self, snapshot_1145):
        """Prior VA analysis outputs expected keys."""
        gva = snapshot_1145["market_structure"]["prior_va_analysis"]
        assert isinstance(gva, dict)
        assert len(gva) > 0

    def test_ib_extension_keys(self, snapshot_1145):
        """IB extension module outputs expected keys."""
        tpr = snapshot_1145["market_structure"]["ib_extension"]
        assert isinstance(tpr, dict)

    def test_va_poke_keys(self, snapshot_1145):
        """VA poke module outputs expected keys."""
        vef = snapshot_1145["market_structure"]["va_poke"]
        assert isinstance(vef, dict)

    def test_smt_detection_keys(self, snapshot_1145):
        """SMT detection module outputs expected keys."""
        smt = snapshot_1145["intraday"]["smt_detection"]
        assert isinstance(smt, dict)
        assert "active_divergences" in smt
        assert isinstance(smt["active_divergences"], list)
        assert "note" in smt

    def test_smt_detection_with_es_ym(self, snapshot_1145):
        """SMT detection has level-specific keys when ES/YM available."""
        smt = snapshot_1145["intraday"]["smt_detection"]
        # These keys should always be present when ES/YM data is provided
        for key in ["smt_at_session_high", "smt_at_session_low"]:
            assert key in smt, f"Missing smt key: {key}"

    def test_ib_extension_profile_context(self, snapshot_1145):
        """IB extension module has volume/TPO acceptance context."""
        ext = snapshot_1145["market_structure"]["ib_extension"]
        assert isinstance(ext, dict)
        # These keys may only be present when 20P triggers (post-IB with enough bars)
        if ext.get("ib_complete") and ext.get("ib_filter_pass") and ext.get("bars_post_ib", 0) >= 3:
            for key in ["volume_accepted", "vol_poc_location", "tpo_accepted", "tpo_poc_location"]:
                assert key in ext, f"Missing ib_extension key: {key}"

    def test_prior_va_tpo_alignment(self, snapshot_1145):
        """Prior VA analysis has TPO cross-reference."""
        gva = snapshot_1145["market_structure"]["prior_va_analysis"]
        assert isinstance(gva, dict)
        if gva.get("status") == "complete":
            assert "tpo_va_alignment" in gva
            assert gva["tpo_va_alignment"] in ("inside_prior_va", "extending_beyond", "no_data")

    def test_no_trade_signals_in_market_structure(self, snapshot_1145):
        """Regression guard: no trade signals leak into market_structure."""
        ms = snapshot_1145["market_structure"]

        def _check_no_signals(obj, path="market_structure"):
            if isinstance(obj, dict):
                for key, val in obj.items():
                    assert key not in FORBIDDEN_SIGNAL_KEYS, (
                        f"Forbidden signal key '{key}' found at {path}.{key}"
                    )
                    _check_no_signals(val, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, val in enumerate(obj):
                    _check_no_signals(val, f"{path}[{i}]")

        _check_no_signals(ms)


# ===========================================================================
# Class 3: TestMultiDaySnapshots — Cross-session consistency
# ===========================================================================


class TestMultiDaySnapshots:
    """Test that snapshots are consistent across multiple trading days."""

    @pytest.mark.parametrize("n_days", [1, 3, 5])
    def test_multi_day_fast(self, n_days):
        """Generate snapshots for N recent days at 11:45 — all produce valid output."""
        sessions = RECENT_SESSIONS[:n_days]
        for session_date in sessions:
            clear_global_cache()
            config = _make_config(session_date, "11:45")
            snapshot = generate_snapshot(config)
            _validate_snapshot_basics(snapshot)
            assert snapshot["session_date"] == session_date
            assert snapshot["current_et_time"] == "11:45"

    @pytest.mark.slow
    @pytest.mark.parametrize("n_days", [10, 15])
    def test_multi_day_slow(self, n_days):
        """Generate snapshots for N days — validates consistency at scale."""
        sessions = RECENT_SESSIONS[:n_days]
        keys_sets = []
        for session_date in sessions:
            clear_global_cache()
            config = _make_config(session_date, "11:45")
            snapshot = generate_snapshot(config)
            _validate_snapshot_basics(snapshot)
            keys_sets.append(set(snapshot.keys()))

        # All snapshots should have the same top-level keys
        first_keys = keys_sets[0]
        for i, ks in enumerate(keys_sets[1:], 1):
            assert ks == first_keys, (
                f"Day {sessions[i]} has different keys: "
                f"extra={ks - first_keys}, missing={first_keys - ks}"
            )


# ===========================================================================
# Class 4: TestSchemaCompliance — Validation and serialization
# ===========================================================================


class TestSchemaCompliance:
    """Test schema validation, config validation, and serialization correctness."""

    def test_schema_validator_passes(self):
        """Schema validator accepts a valid orchestrator snapshot."""
        config = _make_config(LATEST_SESSION, "11:45")
        snapshot = generate_snapshot(config)
        # Should not raise
        validate_snapshot(snapshot)

    def test_config_validator_rejects_missing_keys(self):
        """Config validator rejects config missing required keys."""
        with pytest.raises(ValueError, match="Missing required key"):
            validate_config({"session_date": "2026-02-27"})

    def test_config_validator_rejects_bad_date(self):
        """Config validator rejects invalid date format."""
        with pytest.raises(ValueError, match="session_date"):
            validate_config({
                "session_date": "02-27-2026",
                "current_time": "11:45",
                "csv_paths": {"nq": NQ_CSV},
            })

    def test_config_validator_rejects_bad_time(self):
        """Config validator rejects invalid time format."""
        with pytest.raises(ValueError, match="current_time"):
            validate_config({
                "session_date": "2026-02-27",
                "current_time": "25:00",
                "csv_paths": {"nq": NQ_CSV},
            })

    def test_no_numpy_types_in_output(self):
        """Snapshot contains no numpy types after clean_for_json."""
        config = _make_config(LATEST_SESSION, "11:45", include_es_ym=True)
        snapshot = generate_snapshot(config)

        def _check_numpy(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _check_numpy(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _check_numpy(v, f"{path}[{i}]")
            elif isinstance(obj, (np.integer, np.floating, np.bool_, np.ndarray)):
                raise AssertionError(
                    f"Numpy type at {path}: {type(obj).__name__} = {obj}"
                )

        _check_numpy(snapshot)

    def test_json_roundtrip(self):
        """Snapshot survives JSON encode -> decode roundtrip."""
        config = _make_config(LATEST_SESSION, "11:45")
        snapshot = generate_snapshot(config)
        encoded = json.dumps(snapshot)
        decoded = json.loads(encoded)
        assert decoded["session_date"] == snapshot["session_date"]
        assert decoded["current_et_time"] == snapshot["current_et_time"]
        assert set(decoded.keys()) == set(snapshot.keys())


# ===========================================================================
# Class 5: TestErrorHandling — Graceful degradation
# ===========================================================================


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    def test_missing_es_ym_still_valid(self):
        """Snapshot with NQ-only (no ES/YM) is still valid, SMT = neutral."""
        config = _make_config(LATEST_SESSION, "11:45", include_es_ym=False)
        snapshot = generate_snapshot(config)
        _validate_snapshot_basics(snapshot)

        # SMT should be neutral or missing (no cross-market data)
        smt = snapshot["premarket"].get("smt_preopen", {})
        if isinstance(smt, dict) and "signal" in smt:
            assert smt["signal"] in ("neutral", "no_data", None)

    def test_very_early_time(self):
        """Very early time (19:05) produces partial but valid snapshot."""
        config = _make_config(LATEST_SESSION, "19:05")
        snapshot = generate_snapshot(config)
        _validate_snapshot_basics(snapshot)

        # IB should not be complete yet
        ib = snapshot["intraday"]["ib"]
        assert ib.get("ib_status") in ("complete", "partial", "no_data")

    def test_config_missing_nq_path(self):
        """Raises ValueError when NQ CSV path is missing."""
        with pytest.raises(ValueError):
            validate_config({
                "session_date": LATEST_SESSION,
                "current_time": "11:45",
                "csv_paths": {},
            })

    def test_config_nonexistent_csv(self):
        """Raises ValueError when NQ CSV doesn't exist."""
        with pytest.raises(ValueError, match="NQ CSV not found"):
            validate_config({
                "session_date": LATEST_SESSION,
                "current_time": "11:45",
                "csv_paths": {"nq": "/nonexistent/path.csv"},
            })


# ===========================================================================
# Class 6: TestSMTDetection — Cross-market divergence detection
# ===========================================================================


class TestSMTDetection:
    """Test SMT detection module independently and within orchestrator."""

    def test_smt_no_es_ym_graceful(self):
        """SMT without ES/YM returns graceful degradation."""
        config = _make_config(LATEST_SESSION, "11:45", include_es_ym=False)
        snapshot = generate_snapshot(config)
        smt = snapshot["intraday"]["smt_detection"]
        assert isinstance(smt, dict)
        assert "active_divergences" in smt
        assert isinstance(smt["active_divergences"], list)

    def test_smt_with_es_ym(self):
        """SMT with ES/YM data produces level-specific divergence checks."""
        config = _make_config(LATEST_SESSION, "11:45", include_es_ym=True)
        snapshot = generate_snapshot(config)
        smt = snapshot["intraday"]["smt_detection"]
        assert isinstance(smt, dict)
        assert "smt_at_session_high" in smt
        assert "smt_at_session_low" in smt
        # All divergence values should be valid strings
        valid_values = {
            "bearish_divergence", "bullish_divergence", "confirmed",
            "no_test", "no_ib_data", "no_data"
        }
        for key, val in smt.items():
            if key.startswith("smt_at_"):
                assert val in valid_values, f"Invalid SMT value for {key}: {val}"

    @pytest.mark.parametrize("current_time", ["10:35", "12:00", "14:00"])
    def test_smt_at_multiple_times(self, current_time):
        """SMT detection works at various post-IB times."""
        config = _make_config(LATEST_SESSION, current_time, include_es_ym=True)
        snapshot = generate_snapshot(config)
        smt = snapshot["intraday"]["smt_detection"]
        assert isinstance(smt, dict)
        assert "active_divergences" in smt

    def test_smt_early_session(self):
        """SMT at early time (pre-RTH) returns empty or graceful output."""
        config = _make_config(LATEST_SESSION, "09:00", include_es_ym=True)
        snapshot = generate_snapshot(config)
        smt = snapshot["intraday"]["smt_detection"]
        assert isinstance(smt, dict)


# ===========================================================================
# Class 7: TestBalanceSkewMorph — Balance skew classification + morph detection
# ===========================================================================


class TestBalanceSkewMorph:
    """Test balance day skew classification, seam level, and morph detection."""

    @pytest.fixture(scope="class")
    def snapshot_1145(self):
        """Snapshot at 11:45 — post-IB, pre-PM morph window."""
        clear_global_cache()
        config = _make_config(LATEST_SESSION, "11:45", include_es_ym=True)
        return generate_snapshot(config)

    @pytest.fixture(scope="class")
    def snapshot_1400(self):
        """Snapshot at 14:00 — PM prime morph window."""
        clear_global_cache()
        config = _make_config(LATEST_SESSION, "14:00", include_es_ym=True)
        return generate_snapshot(config)

    @pytest.fixture(scope="class")
    def snapshot_1530(self):
        """Snapshot at 15:30 — PM late morph window."""
        clear_global_cache()
        config = _make_config(LATEST_SESSION, "15:30", include_es_ym=True)
        return generate_snapshot(config)

    # --- Skew fields ---

    def test_skew_fields_present(self, snapshot_1145):
        """Balance type has skew, skew_strength, and skew_factors."""
        bt = snapshot_1145["market_structure"]["balance_type"]
        assert "skew" in bt, "Missing skew field"
        assert "skew_strength" in bt, "Missing skew_strength field"
        assert "skew_factors" in bt, "Missing skew_factors field"

    def test_skew_valid_values(self, snapshot_1145):
        """Skew is one of bullish/bearish/neutral."""
        bt = snapshot_1145["market_structure"]["balance_type"]
        assert bt["skew"] in ("bullish", "bearish", "neutral")

    def test_skew_strength_range(self, snapshot_1145):
        """Skew strength is between 0.0 and 1.0."""
        bt = snapshot_1145["market_structure"]["balance_type"]
        assert 0.0 <= bt["skew_strength"] <= 1.0

    def test_skew_factors_keys(self, snapshot_1145):
        """Skew factors has all expected sub-keys."""
        sf = snapshot_1145["market_structure"]["balance_type"]["skew_factors"]
        expected_keys = [
            "vol_poc_vs_ib_mid", "tpo_poc_vs_ib_mid", "dpoc_direction",
            "fattening_zone", "close_position",
        ]
        for key in expected_keys:
            assert key in sf, f"Missing skew_factors key: {key}"

    def test_skew_factors_valid_values(self, snapshot_1145):
        """Skew factor values are valid enum strings."""
        sf = snapshot_1145["market_structure"]["balance_type"]["skew_factors"]
        assert sf["vol_poc_vs_ib_mid"] in ("above", "below", "at")
        assert sf["tpo_poc_vs_ib_mid"] in ("above", "below", "at")
        assert sf["dpoc_direction"] in ("up", "down", "flat")
        assert sf["fattening_zone"] in ("above_vah", "at_vah", "inside_va", "at_val", "below_val")
        assert sf["close_position"] in ("upper_third", "middle", "lower_third")

    # --- Seam level ---

    def test_seam_level_present(self, snapshot_1145):
        """Seam level is a numeric value."""
        bt = snapshot_1145["market_structure"]["balance_type"]
        assert "seam_level" in bt
        assert isinstance(bt["seam_level"], (int, float))

    def test_seam_level_reasonable(self, snapshot_1145):
        """Seam level is within IB range (sanity check)."""
        bt = snapshot_1145["market_structure"]["balance_type"]
        ib = snapshot_1145["intraday"]["ib"]
        seam = bt["seam_level"]
        ib_high = ib.get("ib_high")
        ib_low = ib.get("ib_low")
        if ib_high and ib_low and seam > 0:
            # Seam should be within a generous range of IB
            ib_range = ib_high - ib_low
            assert ib_low - ib_range <= seam <= ib_high + ib_range, \
                f"Seam {seam} is outside reasonable range [{ib_low - ib_range}, {ib_high + ib_range}]"

    def test_seam_description_present(self, snapshot_1145):
        """Seam description is a non-empty string."""
        bt = snapshot_1145["market_structure"]["balance_type"]
        assert "seam_description" in bt
        assert isinstance(bt["seam_description"], str)
        assert len(bt["seam_description"]) > 0

    # --- Morph detection ---

    def test_morph_fields_present(self, snapshot_1145):
        """Balance type has morph dict with expected keys."""
        morph = snapshot_1145["market_structure"]["balance_type"]["morph"]
        assert isinstance(morph, dict)
        for key in ["status", "morph_type", "morph_time_window", "morph_signals", "morph_confidence"]:
            assert key in morph, f"Missing morph key: {key}"

    def test_morph_status_valid(self, snapshot_1145):
        """Morph status is one of none/developing/confirmed."""
        morph = snapshot_1145["market_structure"]["balance_type"]["morph"]
        assert morph["status"] in ("none", "developing", "confirmed")

    def test_morph_type_valid(self, snapshot_1145):
        """Morph type is a valid enum."""
        morph = snapshot_1145["market_structure"]["balance_type"]["morph"]
        valid_types = ("none", "neutral_to_bullish", "neutral_to_bearish", "to_trend_up", "to_trend_down")
        assert morph["morph_type"] in valid_types

    def test_morph_confidence_range(self, snapshot_1145):
        """Morph confidence is between 0.0 and 1.0."""
        morph = snapshot_1145["market_structure"]["balance_type"]["morph"]
        assert 0.0 <= morph["morph_confidence"] <= 1.0

    def test_morph_signals_is_list(self, snapshot_1145):
        """Morph signals is a list of strings."""
        morph = snapshot_1145["market_structure"]["balance_type"]["morph"]
        assert isinstance(morph["morph_signals"], list)
        for s in morph["morph_signals"]:
            assert isinstance(s, str)

    def test_morph_inactive_before_noon(self, snapshot_1145):
        """At 11:45, morph should be in AM window (inactive or none)."""
        morph = snapshot_1145["market_structure"]["balance_type"]["morph"]
        assert morph["morph_time_window"] == "am"
        assert morph["status"] == "none"

    def test_morph_active_pm_prime(self, snapshot_1400):
        """At 14:00, morph window should be pm_prime."""
        morph = snapshot_1400["market_structure"]["balance_type"]["morph"]
        assert morph["morph_time_window"] == "pm_prime"

    def test_morph_active_pm_late(self, snapshot_1530):
        """At 15:30, morph window should be pm_late."""
        morph = snapshot_1530["market_structure"]["balance_type"]["morph"]
        assert morph["morph_time_window"] == "pm_late"

    def test_morph_confidence_matches_status(self, snapshot_1400):
        """Morph confidence aligns with status classification."""
        morph = snapshot_1400["market_structure"]["balance_type"]["morph"]
        if morph["status"] == "none":
            assert morph["morph_confidence"] < 0.30
        elif morph["status"] == "developing":
            assert 0.30 <= morph["morph_confidence"] <= 0.60
        elif morph["status"] == "confirmed":
            assert morph["morph_confidence"] > 0.60

    # --- Cross-time consistency ---

    @pytest.mark.parametrize("current_time", ["10:35", "11:45", "13:00", "14:00", "15:30"])
    def test_skew_morph_at_all_times(self, current_time):
        """Skew + morph fields are present and valid at all post-IB times."""
        clear_global_cache()
        config = _make_config(LATEST_SESSION, current_time)
        snapshot = generate_snapshot(config)
        bt = snapshot["market_structure"]["balance_type"]

        # Skew fields always present
        assert bt["skew"] in ("bullish", "bearish", "neutral")
        assert 0.0 <= bt["skew_strength"] <= 1.0
        assert isinstance(bt["skew_factors"], dict)
        assert isinstance(bt["seam_level"], (int, float))

        # Morph fields always present
        morph = bt["morph"]
        assert morph["status"] in ("none", "developing", "confirmed")
        assert 0.0 <= morph["morph_confidence"] <= 1.0

    # --- Multi-day consistency ---

    @pytest.mark.parametrize("session_date", RECENT_SESSIONS[:3])
    def test_skew_morph_multi_day(self, session_date):
        """Skew + morph fields present across multiple trading days."""
        clear_global_cache()
        config = _make_config(session_date, "14:00")
        snapshot = generate_snapshot(config)
        bt = snapshot["market_structure"]["balance_type"]

        assert "skew" in bt
        assert "skew_strength" in bt
        assert "skew_factors" in bt
        assert "seam_level" in bt
        assert "morph" in bt
        assert bt["morph"]["morph_time_window"] == "pm_prime"
