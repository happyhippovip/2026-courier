#!/usr/bin/env python3
"""Retired unsafe evidence injector.

Physical acceptance evidence must be produced by the canonical runtime and
validated by an independent verifier.  A local helper must never be able to
manufacture a VALID machine artifact or write it into the Ledger.
"""

import sys

def main():
    print(
        "REFUSED: local evidence injection is disabled; use independently "
        "verified, exact-runtime physical acceptance evidence.",
        file=sys.stderr,
    )
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
