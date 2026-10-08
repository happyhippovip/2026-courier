#!/usr/bin/env python3
"""Provider health check placeholder.

STUB: performs no provider validation. Exits non-zero so no acceptance
gate can mistake this script for a passing health check. Remove this stub
when a real check lands (see the provider_survival / provider_circuit
lanes, which own live provider state).
"""
import sys


def main():
    print("STUB: provider_health_check performs no validation.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
