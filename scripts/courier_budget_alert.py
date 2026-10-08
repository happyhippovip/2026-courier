#!/usr/bin/env python3
"""Budget alert placeholder.

STUB: performs no budget measurement. Exits non-zero so no cost gate can
mistake this script for a passing budget check. Remove this stub when a
real check lands (see the cost-aware routing / resource-policy lanes,
which own live budget state).
"""
import sys


def main():
    print("STUB: courier_budget_alert performs no budget measurement.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
