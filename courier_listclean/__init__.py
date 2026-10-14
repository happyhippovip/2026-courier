"""Deterministic local cleaner for the 39 EUR list offer.

No network. No model calls. The source file is never modified.
The change report does not include a price.

Known limitations:

- Line breaks inside a field become spaces.
- original_row_id is the record number for multi-line fields.
- The ' | ' separator in Zusatzspalten is ambiguous.
"""

from .clean import MAX_ROWS, CleanResult, Finding, ListCleanError, clean_table

__all__ = [
    "MAX_ROWS",
    "CleanResult",
    "Finding",
    "ListCleanError",
    "clean_table",
]
