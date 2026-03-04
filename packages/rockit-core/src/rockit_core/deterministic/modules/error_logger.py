# modules/error_logger.py
"""
Error logging for orchestrator failures.
Logs errors to file to prevent silent failures and aid debugging.
"""

import os
import json
from datetime import datetime


class ErrorLogger:
    """
    Logs errors to a JSON file for analysis and debugging.

    Usage:
        logger = ErrorLogger('error_log.txt')
        try:
            do_something()
        except Exception as e:
            logger.log('do_something', e, {'context': 'value'})
    """

    def __init__(self, log_path='error_log.txt'):
        """
        Initialize error logger.

        Args:
            log_path (str): Path to error log file
        """
        self.log_path = log_path
        self.errors = []

    def log(self, function_name, exception, context=None):
        """
        Log an error to file and memory.

        Args:
            function_name (str): Name of function that failed
            exception (Exception): The exception that was raised
            context (dict): Optional context dict (e.g., {'session_date': '2026-02-20'})
        """
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "function": function_name,
            "error_type": type(exception).__name__,
            "error_message": str(exception),
            "context": context or {}
        }

        self.errors.append(error_entry)
        self._write_to_file(error_entry)

    def _write_to_file(self, error_entry):
        """
        Append error entry to log file (JSONL format).

        Args:
            error_entry (dict): Error entry to write
        """
        try:
            os.makedirs(os.path.dirname(self.log_path) or '.', exist_ok=True)
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(error_entry) + '\n')
        except Exception as e:
            print(f"Warning: Could not write to error log: {e}")

    def get_errors(self):
        """
        Get all logged errors.

        Returns:
            list: List of error entry dicts
        """
        return self.errors

    def clear(self):
        """Clear in-memory errors (file is not deleted)."""
        self.errors.clear()

    def stats(self):
        """
        Get error statistics.

        Returns:
            dict: Count by error type
        """
        stats = {}
        for error in self.errors:
            error_type = error.get('error_type', 'unknown')
            stats[error_type] = stats.get(error_type, 0) + 1
        return stats

    def __repr__(self):
        """Return logger status."""
        return f"ErrorLogger(path={self.log_path}, errors={len(self.errors)})"


# Global singleton error logger
_global_logger = ErrorLogger('error_log.txt')


def get_global_logger():
    """Get global singleton error logger."""
    return _global_logger


def log_error(function_name, exception, context=None):
    """Log error to global singleton logger."""
    _global_logger.log(function_name, exception, context)
