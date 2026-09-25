import sys
from pathlib import Path

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "scripts"))
import cannon_yolo as y

import tests.test_cannon_yolo as tcy

# Override the timeout for delta test
def patched_make(W, mode, **extra):
    e = {**W.env, "FAKE_MODE": mode, **extra}
    if mode == "delta":
        e["COURIER_YOLO_IDLE_SECONDS"] = "10"
    return y.Yolo({}, env=e), e

tcy.make = patched_make

import pytest
sys.exit(pytest.main(["-v", "tests/test_cannon_yolo.py::test_u_duplicate_and_streamed_block_still_done"]))
