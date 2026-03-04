"""Tests for SessionDataManager — zip extraction, delta merge, dedup, info."""

import zipfile
from pathlib import Path

import pandas as pd
import pytest

from rockit_core.data.manager import SessionDataManager


# --- Fixtures ---

SAMPLE_HEADER = "#schema: NinjaDataExport/v2.3, volumetric=True\n"
SAMPLE_COLUMNS = (
    "timestamp,instrument,period,open,high,low,close,volume,"
    "ema20,ema50,ema200,rsi14,atr14,vwap,vwap_upper1,vwap_upper2,vwap_upper3,"
    "vwap_lower1,vwap_lower2,vwap_lower3,vol_ask,vol_bid,vol_delta,session_date\n"
)


def _make_row(ts: str, instrument: str = "NQ", session_date: str = "2025-03-01") -> str:
    return (
        f"{ts},{instrument},Volumetric_1,100,101,99,100.5,500,"
        f"100,100,100,50,10,100,101,102,103,99,98,97,300,200,100,{session_date}\n"
    )


def _make_csv_content(rows: list[str]) -> str:
    return SAMPLE_HEADER + SAMPLE_COLUMNS + "".join(rows)


def _write_csv(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_zip(zip_path: Path, csv_name: str, csv_content: str):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(csv_name, csv_content)


# --- Tests ---


class TestSessionDataManagerLoad:
    """Tests for the load() method."""

    def test_load_from_csv(self, tmp_path):
        """Load from existing CSV in data_dir."""
        rows = [
            _make_row("2025-03-01T10:00:00.000", session_date="2025-03-01"),
            _make_row("2025-03-01T10:01:00.000", session_date="2025-03-01"),
        ]
        _write_csv(tmp_path / "NQ_Volumetric_1.csv", _make_csv_content(rows))

        mgr = SessionDataManager(data_dir=tmp_path)
        df = mgr.load("NQ")

        assert len(df) == 2
        assert df["instrument"].iloc[0] == "NQ"

    def test_load_from_zip(self, tmp_path):
        """Load by extracting from zip when CSV doesn't exist."""
        rows = [
            _make_row("2025-03-01T10:00:00.000", session_date="2025-03-01"),
            _make_row("2025-03-02T10:00:00.000", session_date="2025-03-02"),
            _make_row("2025-03-03T10:00:00.000", session_date="2025-03-03"),
        ]
        csv_content = _make_csv_content(rows)
        _write_zip(
            tmp_path / "NQ_Volumetric_1.zip",
            "NQ_Volumetric_1.csv",
            csv_content,
        )

        mgr = SessionDataManager(data_dir=tmp_path)
        df = mgr.load("NQ")

        assert len(df) == 3
        # Verify CSV was extracted
        assert (tmp_path / "NQ_Volumetric_1.csv").exists()

    def test_load_from_baseline_dir(self, tmp_path):
        """Load from separate baseline directory."""
        data_dir = tmp_path / "data"
        baseline_dir = tmp_path / "baseline"

        rows = [_make_row("2025-03-01T10:00:00.000", session_date="2025-03-01")]
        _write_csv(baseline_dir / "NQ_Volumetric_1.csv", _make_csv_content(rows))

        mgr = SessionDataManager(data_dir=data_dir, baseline_dir=baseline_dir)
        df = mgr.load("NQ")

        assert len(df) == 1

    def test_load_case_insensitive(self, tmp_path):
        """Instrument name should be case-insensitive."""
        rows = [_make_row("2025-03-01T10:00:00.000", session_date="2025-03-01")]
        _write_csv(tmp_path / "NQ_Volumetric_1.csv", _make_csv_content(rows))

        mgr = SessionDataManager(data_dir=tmp_path)
        df = mgr.load("nq")
        assert len(df) == 1

    def test_load_missing_raises(self, tmp_path):
        """Raise FileNotFoundError when no data available."""
        mgr = SessionDataManager(data_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            mgr.load("NQ")


class TestSessionDataManagerMerge:
    """Tests for the merge_delta() method."""

    def test_merge_adds_new_rows(self, tmp_path):
        """New rows from delta are added."""
        data_dir = tmp_path / "data"
        delta_dir = tmp_path / "delta"

        baseline_rows = [
            _make_row("2025-03-01T10:00:00.000", session_date="2025-03-01"),
            _make_row("2025-03-01T10:01:00.000", session_date="2025-03-01"),
        ]
        delta_rows = [
            _make_row("2025-03-02T10:00:00.000", session_date="2025-03-02"),
            _make_row("2025-03-02T10:01:00.000", session_date="2025-03-02"),
        ]

        _write_csv(data_dir / "NQ_Volumetric_1.csv", _make_csv_content(baseline_rows))
        _write_csv(delta_dir / "NQ_Volumetric_1.csv", _make_csv_content(delta_rows))

        mgr = SessionDataManager(data_dir=data_dir, delta_dir=delta_dir)
        merged = mgr.merge_delta("NQ")

        assert len(merged) == 4
        assert merged["session_date"].nunique() == 2

    def test_merge_deduplicates(self, tmp_path):
        """Overlapping rows are deduplicated."""
        data_dir = tmp_path / "data"
        delta_dir = tmp_path / "delta"

        # Same row in both baseline and delta
        shared_row = _make_row("2025-03-01T10:00:00.000", session_date="2025-03-01")
        new_row = _make_row("2025-03-02T10:00:00.000", session_date="2025-03-02")

        _write_csv(data_dir / "NQ_Volumetric_1.csv", _make_csv_content([shared_row]))
        _write_csv(delta_dir / "NQ_Volumetric_1.csv", _make_csv_content([shared_row, new_row]))

        mgr = SessionDataManager(data_dir=data_dir, delta_dir=delta_dir)
        merged = mgr.merge_delta("NQ")

        assert len(merged) == 2  # shared + new, not 3

    def test_merge_saves_to_data_dir(self, tmp_path):
        """Merged CSV is saved back to data_dir."""
        data_dir = tmp_path / "data"
        delta_dir = tmp_path / "delta"

        _write_csv(
            data_dir / "NQ_Volumetric_1.csv",
            _make_csv_content([_make_row("2025-03-01T10:00:00.000", session_date="2025-03-01")]),
        )
        _write_csv(
            delta_dir / "NQ_Volumetric_1.csv",
            _make_csv_content([_make_row("2025-03-02T10:00:00.000", session_date="2025-03-02")]),
        )

        mgr = SessionDataManager(data_dir=data_dir, delta_dir=delta_dir)
        mgr.merge_delta("NQ")

        # Verify the merged file was saved
        saved = pd.read_csv(data_dir / "NQ_Volumetric_1.csv")
        assert len(saved) == 2

    def test_merge_missing_delta_returns_baseline(self, tmp_path):
        """When delta file doesn't exist, return baseline unchanged."""
        data_dir = tmp_path / "data"
        rows = [_make_row("2025-03-01T10:00:00.000", session_date="2025-03-01")]
        _write_csv(data_dir / "NQ_Volumetric_1.csv", _make_csv_content(rows))

        mgr = SessionDataManager(data_dir=data_dir, delta_dir=tmp_path / "nonexistent")
        result = mgr.merge_delta("NQ")

        assert len(result) == 1

    def test_merge_explicit_delta_path(self, tmp_path):
        """Can pass explicit delta_path."""
        data_dir = tmp_path / "data"
        delta_file = tmp_path / "custom" / "NQ_delta.csv"

        _write_csv(
            data_dir / "NQ_Volumetric_1.csv",
            _make_csv_content([_make_row("2025-03-01T10:00:00.000", session_date="2025-03-01")]),
        )
        _write_csv(
            delta_file,
            _make_csv_content([_make_row("2025-03-02T10:00:00.000", session_date="2025-03-02")]),
        )

        mgr = SessionDataManager(data_dir=data_dir)
        merged = mgr.merge_delta("NQ", delta_path=delta_file)

        assert len(merged) == 2


class TestSessionDataManagerInfo:
    """Tests for the info() method."""

    def test_info_returns_correct_data(self, tmp_path):
        """Info returns correct session count and date range."""
        rows = [
            _make_row("2025-03-01T10:00:00.000", session_date="2025-03-01"),
            _make_row("2025-03-01T10:01:00.000", session_date="2025-03-01"),
            _make_row("2025-03-02T10:00:00.000", session_date="2025-03-02"),
        ]
        _write_csv(tmp_path / "NQ_Volumetric_1.csv", _make_csv_content(rows))

        mgr = SessionDataManager(data_dir=tmp_path)
        info = mgr.info("NQ")

        assert info["instrument"] == "NQ"
        assert info["rows"] == 3
        assert info["sessions"] == 2
