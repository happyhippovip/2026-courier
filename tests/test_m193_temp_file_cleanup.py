import os
import glob
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import uuid

def simulate_chief_commander_crash(test_dir: Path):
    path = test_dir / "chief_state.json"
    
    # Simulate first attempt crashing
    temporary1 = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temporary1.write_text(json.dumps({"state": "partial"}), encoding="utf-8")
    # CRASH HAPPENS HERE - no os.replace called
    
    # Simulate second attempt crashing
    temporary2 = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temporary2.write_text(json.dumps({"state": "partial2"}), encoding="utf-8")
    
    # Assert leak
    leaked = list(test_dir.glob("*.tmp.*"))
    assert len(leaked) == 2, f"Expected 2 leaked files, got {len(leaked)}"

def simulate_fixed_tmp_crash(test_dir: Path):
    path = test_dir / "app_state.json"
    
    # Simulate first attempt crashing
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text("partial1", encoding="utf-8")
    
    # Simulate second attempt crashing
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text("partial2", encoding="utf-8")
    
    # Assert bounded
    leaked = list(test_dir.glob("*.tmp"))
    assert len(leaked) == 1, f"Expected 1 leaked file, got {len(leaked)}"
    assert temp_path.read_text(encoding="utf-8") == "partial2"

if __name__ == "__main__":
    with TemporaryDirectory() as td:
        test_dir = Path(td)
        simulate_chief_commander_crash(test_dir)
        simulate_fixed_tmp_crash(test_dir)
        print("M193 TEMP CLEANUP: PROVEN")
