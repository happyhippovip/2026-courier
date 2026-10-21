#!/usr/bin/env python3
"""Provider Health Check and Zero-Cost CLI Capability Verifier (S04)."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure root is in sys.path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from courier_core.provider_detector import detect_all_providers


def main() -> int:
    results = detect_all_providers()
    print("Provider Health & CLI Verification:")
    for prov, res in results.items():
        status = "ONLINE" if res.available else "OFFLINE/UNAVAILABLE"
        print(f"  - {prov:6}: {status:19} (version={res.version}, reason={res.reason})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
