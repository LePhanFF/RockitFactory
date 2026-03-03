#!/usr/bin/env python3
"""
Outcome Labeling System

Retroactively computes what price did 5/10/15/30 minutes after each snapshot,
enabling LLM to learn from actual market outcomes and calibrate confidence scores.

This is critical for training: the LLM learns "when I said 75% confident, did I win?"
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional


class OutcomeLabeler:
    """Computes retroactive outcome labels for training entries"""

    def __init__(self, df_extended: pd.DataFrame):
        """
        Args:
            df_extended: Full historical DataFrame with all market data
                         Index must be DatetimeIndex with timezone aware
        """
        self.df = df_extended.copy()
        # Ensure index is datetime
        if not isinstance(self.df.index, pd.DatetimeIndex):
            self.df.index = pd.to_datetime(self.df.index)

    def compute_outcome_label(self, snapshot_entry: Dict, current_time_str: str) -> Dict:
        """
        Compute outcome label for a single snapshot entry.

        Args:
            snapshot_entry: dict with 'input' and 'output' (training entry)
            current_time_str: Time string like "09:30" or "11:45"

        Returns:
            outcome_label dict with:
                - forward_prices: High/Low/Close at 5/10/15/30 min ahead
                - trade_setup: Entry price, stop, targets from playbook
                - trade_outcome: What actually happened
                - confidence_validation: Predicted vs actual result
        """
        session_date = snapshot_entry["input"].get("session_date", "")

        # Parse the snapshot time
        try:
            snapshot_dt = pd.to_datetime(f"{session_date} {current_time_str}")
        except Exception as e:
            return {"error": f"Failed to parse time: {e}"}

        # Look forward: 5, 10, 15, 30 minutes
        forward_prices = self._get_forward_prices(snapshot_dt)

        if not forward_prices:
            return {"status": "no_forward_data"}

        # Extract playbook details from output
        playbook_info = self._extract_playbook_info(snapshot_entry)

        # Compute trade outcome
        trade_outcome = self._compute_trade_outcome(
            playbook_info, forward_prices, snapshot_dt
        )

        # Validate confidence
        confidence_validation = self._validate_confidence(
            snapshot_entry, trade_outcome
        )

        return {
            "timestamp": snapshot_dt.isoformat(),
            "forward_prices": forward_prices,
            "playbook_setup": playbook_info,
            "trade_outcome": trade_outcome,
            "confidence_validation": confidence_validation,
            "session_date": session_date,
            "snapshot_time": current_time_str,
        }

    def _get_forward_prices(
        self, snapshot_dt: pd.Timestamp
    ) -> Optional[Dict]:
        """Get price data for 5/10/15/30 minutes ahead"""
        forward_prices = {}

        for minutes_ahead in [5, 10, 15, 30]:
            target_time = snapshot_dt + timedelta(minutes=minutes_ahead)

            # Get candle for that time
            future_candle = self.df[
                (self.df.index >= target_time)
                & (self.df.index < target_time + timedelta(minutes=5))
            ]

            if future_candle.empty:
                continue

            forward_prices[f"{minutes_ahead}m"] = {
                "high": float(future_candle["high"].max()),
                "low": float(future_candle["low"].min()),
                "close": float(future_candle.iloc[-1]["close"]),
                "timestamp": future_candle.index[-1].isoformat(),
            }

        return forward_prices if forward_prices else None

    def _extract_playbook_info(self, snapshot_entry: Dict) -> Dict:
        """Extract trading setup from output"""
        output = snapshot_entry.get("output", "")

        # For now, extract from text output
        # In future: will be structured JSON in output
        return {
            "type": "Unknown",  # Will be parsed from output
            "entry_price": None,
            "stop_price": None,
            "target_1": None,
            "target_2": None,
            "confidence": self._extract_confidence(output),
        }

    def _extract_confidence(self, output_text: str) -> Optional[int]:
        """Extract confidence percentage from output text"""
        import re

        if isinstance(output_text, str):
            match = re.search(r"Confidence.*?(\d+)%", output_text)
            if match:
                return int(match.group(1))
        return None

    def _compute_trade_outcome(
        self,
        playbook_info: Dict,
        forward_prices: Dict,
        snapshot_dt: pd.Timestamp,
    ) -> Dict:
        """
        Compute what happened to the trade.

        Since we don't have structured entry/stop/target yet, compute directional outcome.
        """
        if not forward_prices:
            return {"status": "no_data"}

        # Get snapshot price (close of that 5-min bar)
        bar = self.df[
            (self.df.index >= snapshot_dt)
            & (self.df.index < snapshot_dt + timedelta(minutes=5))
        ]

        if bar.empty:
            return {"status": "snapshot_bar_not_found"}

        entry_price = float(bar.iloc[-1]["close"])

        # Look at max drawdown/profit over next 30 min
        max_forward_high = max(
            p["high"] for p in forward_prices.values() if "high" in p
        )
        max_forward_low = min(
            p["low"] for p in forward_prices.values() if "low" in p
        )
        final_close = forward_prices.get("30m", {}).get("close", entry_price)

        # Compute max profit/loss opportunities
        max_profit_if_long = max_forward_high - entry_price
        max_loss_if_long = entry_price - max_forward_low

        max_profit_if_short = entry_price - max_forward_low
        max_loss_if_short = max_forward_high - entry_price

        return {
            "entry_price": round(entry_price, 2),
            "final_close_30m": round(final_close, 2),
            "directional_move_30m": round(final_close - entry_price, 2),
            "max_profit_if_long": round(max_profit_if_long, 2),
            "max_loss_if_long": round(max_loss_if_long, 2),
            "max_profit_if_short": round(max_profit_if_short, 2),
            "max_loss_if_short": round(max_loss_if_short, 2),
            "direction_30m": "UP" if final_close > entry_price else "DOWN",
            "volatility_30m": round(max_forward_high - max_forward_low, 2),
        }

    def _validate_confidence(
        self, snapshot_entry: Dict, trade_outcome: Dict
    ) -> Dict:
        """
        Validate: Predicted confidence vs actual outcome

        Returns calibration assessment
        """
        predicted_conf = self._extract_confidence(
            snapshot_entry.get("output", "")
        )

        if predicted_conf is None:
            return {"status": "no_confidence_extracted"}

        if "error" in trade_outcome or "status" in trade_outcome:
            return {
                "predicted_confidence": predicted_conf,
                "actual_outcome": "UNKNOWN",
                "calibration": "UNCALIBRATED",
            }

        # Simple calibration: did direction match?
        # (More sophisticated: check if confidence matches win rate)
        direction = trade_outcome.get("direction_30m", "")
        move_pts = trade_outcome.get("directional_move_30m", 0)

        # If high confidence (>65%) and moved >10pts in that direction: GOOD
        # If high confidence but moved opposite direction: BAD
        # If low confidence and moved: OK, trade was hard to call

        if predicted_conf >= 65:
            if abs(move_pts) > 10:
                calibration = "WELL_CALIBRATED"
                outcome = "HIGH_CONFIDENCE_WIN" if move_pts > 0 else "HIGH_CONFIDENCE_LOSS"
            else:
                calibration = "POOR_CALIBRATION"
                outcome = "HIGH_CONFIDENCE_CHOP"
        else:
            calibration = "CONSERVATIVE"
            outcome = "LOW_CONFIDENCE" if abs(move_pts) < 15 else "OUTCOME_VARIED"

        return {
            "predicted_confidence": predicted_conf,
            "actual_outcome": outcome,
            "directional_move_30m": trade_outcome.get("directional_move_30m", 0),
            "calibration": calibration,
        }


def add_outcome_labels_to_jsonl(
    input_jsonl_path: str,
    df_extended: pd.DataFrame,
    output_jsonl_path: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Read JSONL file, add outcome labels, write back (or to new file).

    Args:
        input_jsonl_path: Path to training JSONL file
        df_extended: Full historical DataFrame
        output_jsonl_path: Output file path (defaults to input path with .labeled suffix)

    Returns:
        (total_entries, successfully_labeled)
    """
    if output_jsonl_path is None:
        output_jsonl_path = input_jsonl_path.replace(".jsonl", ".labeled.jsonl")

    labeler = OutcomeLabeler(df_extended)
    total = 0
    successful = 0

    with open(input_jsonl_path, "r") as f_in, open(output_jsonl_path, "w") as f_out:
        for line in f_in:
            if not line.strip():
                continue

            total += 1
            try:
                entry = json.loads(line)

                # Infer current_time from entry (if available)
                current_time = entry.get("timestamp", "").split("T")[1][:5] if "timestamp" in entry else "11:45"

                # Compute outcome label
                outcome_label = labeler.compute_outcome_label(entry, current_time)

                # Add to entry
                entry["outcome_label"] = outcome_label

                # Write enhanced entry
                f_out.write(json.dumps(entry) + "\n")
                successful += 1

            except Exception as e:
                print(f"Error processing entry {total}: {e}")
                # Still write original entry
                f_out.write(line)

    return total, successful


if __name__ == "__main__":
    import sys
    from rockit_core.deterministic.modules.loader import load_nq_csv

    if len(sys.argv) < 2:
        print("Usage: python outcome_labeling.py <jsonl_file> [csv_file]")
        print("Example: python outcome_labeling.py data/lora/2026-02-20.jsonl data/raw_csv/NQ_...csv")
        sys.exit(1)

    jsonl_path = sys.argv[1]
    csv_path = sys.argv[2] if len(sys.argv) > 2 else None

    if csv_path is None:
        print("ERROR: Must specify CSV file for historical price data")
        sys.exit(1)

    # Load historical data
    df_ext, _ = load_nq_csv(csv_path, "2026-02-20")

    # Add outcome labels
    total, successful = add_outcome_labels_to_jsonl(jsonl_path, df_ext)
    print(f"Processed {total} entries, successfully labeled {successful}")
