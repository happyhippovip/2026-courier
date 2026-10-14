"""Deterministic local cleaner for the 39 EUR list offer.

No network. No model calls. The source file is never modified.
"""

from .clean import MAX_ROWS, CleanResult, Finding, ListCleanError, clean_table

__all__ = [
    "MAX_ROWS",
    "CleanResult",
    "Finding",
    "ListCleanError",
    "clean_table",
]
