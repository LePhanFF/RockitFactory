"""
Session data manager — load baseline CSVs, merge daily deltas, track sessions.

Supports two baseline sources:
  1. Extracted CSVs (e.g., BookMapOrderFlowStudies-2/csv/)
  2. Zip archives in data/sessions/ (extracted on first load)

Delta source defaults to G:/My Drive/future_data/1min/ (NinjaTrader daily output).
"""

import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd


# Default paths
_DEFAULT_DATA_DIR = Path("data/sessions")
_DEFAULT_DELTA_DIR = Path("G:/My Drive/future_data/1min")


class SessionDataManager:
    """Manages session data: load from CSV/zip, merge deltas, export."""

    def __init__(
        self,
        data_dir: Optional[str | Path] = None,
        baseline_dir: Optional[str | Path] = None,
        delta_dir: Optional[str | Path] = None,
    ):
        """
        Args:
            data_dir: Working directory for merged CSVs (default: data/sessions/).
            baseline_dir: Directory with baseline CSVs (e.g., BookMapOrderFlowStudies-2/csv/).
                          If None, falls back to data_dir (extracts from zip if needed).
            delta_dir: Directory with incremental CSVs (default: G:/My Drive/future_data/1min/).
        """
        self.data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        self.baseline_dir = Path(baseline_dir) if baseline_dir else None
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
        """Extract zip from data_dir, return path to extracted CSV."""
        zip_path = self.data_dir / self._zip_filename(instrument)
        if not zip_path.exists():
            raise FileNotFoundError(f"Zip not found: {zip_path}")

        csv_name = self._csv_filename(instrument)
        out_path = self.data_dir / csv_name

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find the CSV inside the zip (may be nested)
            csv_members = [m for m in zf.namelist() if m.endswith(".csv")]
            if not csv_members:
                raise FileNotFoundError(f"No CSV found inside {zip_path}")

            # Extract the first CSV
            member = csv_members[0]
            with zf.open(member) as src, open(out_path, "wb") as dst:
                dst.write(src.read())

        print(f"Extracted: {zip_path.name} -> {out_path.name}")
        return out_path

    def load(self, instrument: str = "NQ") -> pd.DataFrame:
        """
        Load session data for an instrument.

        Priority:
          1. Merged CSV in data_dir (if exists)
          2. Baseline CSV from baseline_dir (if configured)
          3. Extract from zip in data_dir
        """
        instrument = instrument.upper()
        csv_name = self._csv_filename(instrument)

        # 1. Check for existing merged CSV in data_dir
        merged_path = self.data_dir / csv_name
        if merged_path.exists():
            df = self._read_csv(merged_path)
            return df

        # 2. Try baseline_dir
        if self.baseline_dir is not None:
            baseline_path = self.baseline_dir / csv_name
            if baseline_path.exists():
                df = self._read_csv(baseline_path)
                return df

        # 3. Extract from zip
        extracted = self._extract_zip(instrument)
        df = self._read_csv(extracted)
        return df

    def merge_delta(
        self,
        instrument: str = "NQ",
        delta_path: Optional[str | Path] = None,
    ) -> pd.DataFrame:
        """
        Merge incremental delta CSV into baseline data.

        Args:
            instrument: Instrument symbol (NQ, ES, YM).
            delta_path: Path to delta CSV. Defaults to delta_dir/{instrument}_Volumetric_1.csv.

        Returns:
            Merged DataFrame.
        """
        instrument = instrument.upper()

        # Load baseline
        baseline_df = self.load(instrument)
        baseline_rows = len(baseline_df)
        baseline_sessions = baseline_df["session_date"].nunique()

        # Load delta
        if delta_path is None:
            delta_path = self.delta_dir / self._csv_filename(instrument)
        else:
            delta_path = Path(delta_path)

        if not delta_path.exists():
            print(f"Delta not found: {delta_path} — skipping merge")
            return baseline_df

        delta_df = self._read_csv(delta_path)
        delta_rows = len(delta_df)

        # Concat and deduplicate
        merged = pd.concat([baseline_df, delta_df], ignore_index=True)
        before_dedup = len(merged)
        merged = merged.drop_duplicates(subset=["timestamp", "instrument"], keep="last")
        merged = merged.sort_values(["session_date", "timestamp"]).reset_index(drop=True)

        new_rows = len(merged) - baseline_rows
        new_sessions = merged["session_date"].nunique() - baseline_sessions

        print(
            f"Merged {instrument}: {baseline_rows:,} baseline + {delta_rows:,} delta "
            f"= {len(merged):,} total ({before_dedup - len(merged):,} duplicates removed, "
            f"{new_sessions} new sessions)"
        )

        # Save merged CSV to data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.data_dir / self._csv_filename(instrument)
        merged.to_csv(out_path, index=False)
        print(f"Saved: {out_path}")

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
