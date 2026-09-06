#!/usr/bin/env python3
"""Minimal Standalone Sentinel Deployment Package Builder (Mission Infinite Life).

Builds and exports an ultra-lightweight, zero-secret, provider-independent
sentinel package that can run on any secondary node (Mac, Linux mini-PC, Raspberry Pi, VPS, GitHub Action).

Guarantees:
- Zero secrets, tokens, or credentials included.
- Minimal dependencies (pure standard Python 3.8+ library only).
- Zero execution authority embedded in sentinel.
- Standalone health observation and alert publishing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Optional

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
HOST_SURVIVAL_DIR = EVENTS_DIR / "host-survival"
DIST_DIR = HOST_SURVIVAL_DIR / "sentinel_dist"


STANDALONE_SENTINEL_PY = '''#!/usr/bin/env python3
"""Standalone External Sentinel Watcher (Zero-Dependency Python 3)."""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

def get_utc_now():
    return datetime.now(timezone.utc).isoformat()

class StandaloneSentinel:
    def __init__(self, target_url="http://127.0.0.1:8765/health", telemetry_path="external_safe_telemetry.json"):
        self.target_url = target_url
        self.telemetry_path = Path(telemetry_path)
        self.consecutive_misses = 0
        self.missed_threshold = 3

    def inspect_health(self):
        # 1. Try file-based telemetry
        if self.telemetry_path.exists():
            try:
                data = json.loads(self.telemetry_path.read_text(encoding="utf-8"))
                last_hb = data.get("last_heartbeat")
                if last_hb:
                    hb_dt = datetime.fromisoformat(last_hb.replace("Z", "+00:00"))
                    elapsed = (datetime.now(timezone.utc) - hb_dt).total_seconds()
                    if elapsed < 45.0:
                        self.consecutive_misses = 0
                        return "HEALTHY", f"Heartbeat fresh ({elapsed:.1f}s ago)"
            except Exception as e:
                pass

        # 2. Try HTTP probe
        try:
            req = urllib.request.Request(self.target_url, headers={"User-Agent": "Sentinel-Probe/1.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    self.consecutive_misses = 0
                    return "HEALTHY", "HTTP probe OK (200)"
        except Exception:
            pass

        self.consecutive_misses += 1
        if self.consecutive_misses >= self.missed_threshold:
            return "MACHINE_OFFLINE", f"Probe failed ({self.consecutive_misses} consecutive misses)"
        return "HOST_UNREACHABLE", f"Probe missed ({self.consecutive_misses} miss)"

if __name__ == "__main__":
    watcher = StandaloneSentinel()
    status, reason = watcher.inspect_health()
    print(f"[{get_utc_now()}] Sentinel Status: {status} - {reason}")
'''


def build_sentinel_deployment_package(output_dir: Optional[Path] = None) -> Path:
    """Constructs the minimal standalone sentinel deployment bundle."""
    out = output_dir or DIST_DIR
    out.mkdir(parents=True, exist_ok=True)

    # 1. Write standalone sentinel script
    sentinel_script = out / "sentinel_watcher.py"
    sentinel_script.write_text(STANDALONE_SENTINEL_PY.strip() + "\n", encoding="utf-8")
    sentinel_script.chmod(0o755)

    # 2. Write minimal runner script
    runner_sh = out / "run_sentinel.sh"
    runner_sh.write_text("""#!/bin/sh
cd "$(dirname "$0")"
python3 sentinel_watcher.py
""", encoding="utf-8")
    runner_sh.chmod(0o755)

    # 3. Write manifest
    manifest = {
        "package_name": "SENTINEL_STANDALONE_V1",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "target_runtimes": ["macOS", "Linux (x86_64 / aarch64)", "Raspberry Pi OS", "GitHub Actions"],
        "required_python_version": ">=3.8",
        "secrets_included": False,
        "execution_authority_included": False,
        "files": ["sentinel_watcher.py", "run_sentinel.sh"],
    }
    manifest_file = out / "package_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # 4. Pack into tar.gz bundle
    tar_path = out.parent / "sentinel_deployment_bundle.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(sentinel_script, arcname="sentinel_watcher.py")
        tar.add(runner_sh, arcname="run_sentinel.sh")
        tar.add(manifest_file, arcname="package_manifest.json")

    return tar_path


if __name__ == "__main__":
    bundle = build_sentinel_deployment_package()
    print(f"✅ Sentinel Deployment Package Built: {bundle}")
