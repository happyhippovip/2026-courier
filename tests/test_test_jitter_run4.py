import runpy
from unittest.mock import patch
from pathlib import Path
import scripts.test_jitter_run4 as jitter_module

def test_measure_jitter_fast(capsys):
    jitter_module.measure_jitter(duration_sec=0.2, interval_sec=0.01)
    
    captured = capsys.readouterr()
    assert "Starting timing-jitter measurement for 0.2s" in captured.out
    assert "Expected interval: 10.000 ms" in captured.out
    assert "Max jitter (deviation):" in captured.out

def test_run_main(capsys):
    script_path = Path(__file__).parent.parent / "scripts" / "test_jitter_run4.py"
    
    # Run the script via runpy (takes ~10 seconds)
    runpy.run_path(str(script_path), run_name="__main__")
    
    captured = capsys.readouterr()
    assert "Starting timing-jitter measurement for 10s" in captured.out
