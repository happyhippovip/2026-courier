#!/usr/bin/env python3
"""Operating ledger placeholder -- fail-closed, non-authoritative.

Canonical Courier truth lives in server/state/central_state.json (runtime)
and agent_handoff_ledger.json (coordination). This module must not fabricate
goals, costs, or revenue. It fails closed so any accidental use is loud.
"""

from __future__ import annotations


class NotAuthoritativeError(RuntimeError):
    """Raised when the non-authoritative stub is used as proof."""


def read_ledger():
    raise NotAuthoritativeError(
        "operating_ledger is not authoritative: use server/state/central_state.json "
        "and agent_handoff_ledger.json instead"
    )


def print_operator_report():
    print("--- OPERATOR REPORT ---")
    print("Status: UNKNOWN (operating_ledger is non-authoritative, no evidence)")


if __name__ == "__main__":
    print_operator_report()
