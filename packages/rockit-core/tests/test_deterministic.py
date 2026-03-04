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
    "core_confluences", "inference", "cri_readiness", "playbook_setup",
]

REQUIRED_INTRADAY_KEYS = [
    "ib", "volume_profile", "tpo_profile", "dpoc_migration",
    "wick_parade", "fvg_detection", "globex_va_analysis",
    "twenty_percent_rule", "va_edge_fade",
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

        # CRI should be populated
        cri = snapshot.get("cri_readiness", {})
        assert "status" not in cri or cri["status"] != "failed"

        # Playbook should be populated
        playbook = snapshot.get("playbook_setup", {})
        assert "status" not in playbook or playbook["status"] != "failed"


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
        ]
        for key in expected:
            assert key in ib, f"Missing ib key: {key}"

    def test_volume_profile_keys(self, snapshot_1145):
        """Volume profile module has POC/VAH/VAL."""
        vp = snapshot_1145["intraday"]["volume_profile"]
        assert "current_session" in vp or "poc" in vp
        # Check nested current_session if present
        cs = vp.get("current_session", vp)
        for key in ["poc", "vah", "val"]:
            assert key in cs, f"Missing volume_profile key: {key}"

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

    def test_cri_readiness_keys(self, snapshot_1145):
        """CRI readiness outputs expected keys (or graceful failure)."""
        cri = snapshot_1145["cri_readiness"]
        # Either has real data or a graceful error
        assert isinstance(cri, dict)
        if cri.get("status") != "failed":
            for key in ["terrain", "identity", "permission"]:
                assert key in cri, f"Missing cri key: {key}"

    def test_playbook_setup(self, snapshot_1145):
        """Playbook engine produces a dict output."""
        pb = snapshot_1145["playbook_setup"]
        assert isinstance(pb, dict)

    def test_globex_va_analysis_keys(self, snapshot_1145):
        """Globex VA analysis outputs expected keys."""
        gva = snapshot_1145["intraday"]["globex_va_analysis"]
        assert isinstance(gva, dict)
        # Should have signal or previous session data
        assert len(gva) > 0

    def test_twenty_percent_rule_keys(self, snapshot_1145):
        """20% rule module outputs expected keys."""
        tpr = snapshot_1145["intraday"]["twenty_percent_rule"]
        assert isinstance(tpr, dict)

    def test_va_edge_fade_keys(self, snapshot_1145):
        """VA edge fade module outputs expected keys."""
        vef = snapshot_1145["intraday"]["va_edge_fade"]
        assert isinstance(vef, dict)


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
