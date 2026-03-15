"""
Session data manager — load accumulated CSVs, merge NinjaTrader 1-min deltas.

Data flow:
  - data/sessions/{INSTRUMENT}_Volumetric_1.csv = accumulated truth (all history)
  - data/sessions/{INSTRUMENT}_Volumetric_1.zip = checked-in seed (extracted on first load)
  - G:/My Drive/future_data/1min/ = NinjaTrader rolling export (~3 weeks)
  - merge_delta() appends new rows from the rolling export, deduplicates, saves back

On first use (no CSV exists), the zip is extracted to create the initial CSV.
After that, merge_delta() appends new NinjaTrader data, saves to CSV, and
rebuilds the zip so the checked-in seed always reflects the latest data.
The CSV is gitignored; only the zip is checked in.
"""

import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd


# Default paths
_DEFAULT_DATA_DIR = Path("data/sessions")
_DEFAULT_DELTA_DIR = Path("G:/My Drive/future_data/1min")

# NinjaTrader only exports ~3 weeks of rolling data (~15 sessions).
# Our accumulated local CSV should always be larger than this.
_MIN_EXPECTED_SESSIONS = 50


class SessionDataManager:
    """Manages session data: load accumulated CSVs, merge NinjaTrader deltas."""

    def __init__(
        self,
        data_dir: Optional[str | Path] = None,
        delta_dir: Optional[str | Path] = None,
    ):
        """
        Args:
            data_dir: Directory with accumulated CSVs/zips (default: data/sessions/).
            delta_dir: Directory with NinjaTrader rolling export (default: G:/My Drive/future_data/1min/).
        """
        self.data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        self.delta_dir = Path(delta_dir) if delta_dir else _DEFAULT_DELTA_DIR

    def _csv_filename(self, instrument: str) -> str:
        return f"{instrument}_Volumetric_1.csv"

    def _zip_filename(self, instrument: str) -> str:
        return f"{instrument}_Volumetric_1.zip"

    def _read_csv(self, path: Path) -> pd.DataFrame:
        """Read a NinjaTrader volumetric CSV (skip #schema line)."""
        df = pd.read_csv(path, low_memory=False, comment="#")
        # Parse timestamps
        df = df[df["timestamp"].astype(str).str.len() >= 19].copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", errors="coerce")
        df = df.dropna(subset=["timestamp"])
        # Parse session_date
        df["session_date"] = pd.to_datetime(df["session_date"], errors="coerce")
        return df

    def _extract_zip(self, instrument: str) -> Path:
        """Extract seed zip to CSV on first load."""
        zip_path = self.data_dir / self._zip_filename(instrument)
        csv_path = self.data_dir / self._csv_filename(instrument)

        if not zip_path.exists():
            raise FileNotFoundError(
                f"No data found for {instrument}: neither {csv_path} nor {zip_path} exist."
            )

        with zipfile.ZipFile(zip_path, "r") as zf:
            csv_members = [m for m in zf.namelist() if m.endswith(".csv")]
            if not csv_members:
                raise FileNotFoundError(f"No CSV found inside {zip_path}")
            with zf.open(csv_members[0]) as src, open(csv_path, "wb") as dst:
                dst.write(src.read())

        print(f"Extracted seed data: {zip_path.name} -> {csv_path.name}")
        return csv_path

    def _update_zip(self, instrument: str) -> None:
        """Rebuild the seed zip from the current CSV so it stays current."""
        csv_path = self.data_dir / self._csv_filename(instrument)
        zip_path = self.data_dir / self._zip_filename(instrument)

        if not csv_path.exists():
            return

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(csv_path, self._csv_filename(instrument))

        zip_mb = zip_path.stat().st_size / 1024 / 1024
        print(f"Updated seed zip: {zip_path.name} ({zip_mb:.1f}MB)")

    def load(self, instrument: str = "NQ") -> pd.DataFrame:
        """
        Load accumulated session data for an instrument.

        If the CSV doesn't exist yet, extracts from the seed zip first.
        """
        instrument = instrument.upper()
        csv_path = self.data_dir / self._csv_filename(instrument)

        # Extract from zip on first load
        if not csv_path.exists():
            csv_path = self._extract_zip(instrument)

        return self._read_csv(csv_path)

    def merge_delta(
        self,
        instrument: str = "NQ",
        delta_path: Optional[str | Path] = None,
    ) -> pd.DataFrame:
        """
        Merge NinjaTrader's rolling 1-min export into accumulated local data.

        Appends new rows from the delta, deduplicates on (timestamp, instrument),
        and saves back. Never loses existing sessions.

        Args:
            instrument: Instrument symbol (NQ, ES, YM).
            delta_path: Path to delta CSV. Defaults to delta_dir/{instrument}_Volumetric_1.csv.

        Returns:
            Merged DataFrame.
        """
        instrument = instrument.upper()

        # Load accumulated local data (extracts from zip on first use)
        local_df = self.load(instrument)
        local_rows = len(local_df)
        local_sessions = local_df["session_date"].nunique()

        # Warn if local data looks truncated (someone may have overwritten
        # the accumulated CSV with just NinjaTrader's rolling window)
        if local_sessions < _MIN_EXPECTED_SESSIONS:
            print(
                f"WARNING: {instrument} has only {local_sessions} sessions "
                f"(expected {_MIN_EXPECTED_SESSIONS}+). The local CSV may have "
                f"been overwritten with NinjaTrader's rolling export."
            )

        # Load delta (NinjaTrader rolling export)
        if delta_path is None:
            delta_path = self.delta_dir / self._csv_filename(instrument)
        else:
            delta_path = Path(delta_path)

        if not delta_path.exists():
            print(f"Delta not found: {delta_path} — skipping merge")
            return local_df

        delta_df = self._read_csv(delta_path)
        delta_rows = len(delta_df)

        # Concat and deduplicate — local rows first, delta rows appended.
        # keep="last" so delta updates any overlapping bars.
        merged = pd.concat([local_df, delta_df], ignore_index=True)
        before_dedup = len(merged)
        merged = merged.drop_duplicates(subset=["timestamp", "instrument"], keep="last")
        merged = merged.sort_values(["session_date", "timestamp"]).reset_index(drop=True)

        merged_sessions = merged["session_date"].nunique()
        new_rows = len(merged) - local_rows
        new_sessions = merged_sessions - local_sessions

        # Safety: merging must NEVER lose sessions. The delta is a rolling
        # window — it can only add sessions, not remove old ones.
        if merged_sessions < local_sessions:
            lost = local_sessions - merged_sessions
            raise ValueError(
                f"MERGE ABORTED for {instrument}: would lose {lost} sessions "
                f"({local_sessions} local → {merged_sessions} merged). "
                f"The local file was NOT modified."
            )

        print(
            f"Merged {instrument}: {local_rows:,} local + {delta_rows:,} delta "
            f"= {len(merged):,} total ({before_dedup - len(merged):,} duplicates removed, "
            f"{new_sessions} new sessions)"
        )

        # Save back to accumulated CSV
        self.data_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.data_dir / self._csv_filename(instrument)
        merged.to_csv(out_path, index=False)
        print(f"Saved: {out_path}")

        # Rebuild the seed zip so it always has the latest accumulated data
        self._update_zip(instrument)

        return merged

    def info(self, instrument: str = "NQ") -> dict:
        """Print and return session data info."""
        instrument = instrument.upper()
        df = self.load(instrument)

        session_count = df["session_date"].nunique()
        date_min = df["session_date"].min()
        date_max = df["session_date"].max()

        info = {
            "instrument": instrument,
            "rows": len(df),
            "sessions": session_count,
            "date_range": (date_min, date_max),
        }

        print(f"{instrument} Data Info:")
        print(f"  Rows:     {len(df):,}")
        print(f"  Sessions: {session_count}")
        print(f"  Range:    {date_min.date()} to {date_max.date()}")

        return info
