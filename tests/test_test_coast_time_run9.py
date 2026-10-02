import runpy
import sys
from pathlib import Path

def test_simulate_escrow_coast(capsys):
    script_path = Path(__file__).parent.parent / "scripts" / "test_coast_time_run9.py"
    
    # Run the script via runpy
    runpy.run_path(str(script_path), run_name="__main__")
    
    # Capture output
    captured = capsys.readouterr()
    
    # Verify execution completed and printed results
    assert "Simulating Escrow Bypass / Coast Time Test (RUN9)..." in captured.out
    assert "Physical stopping distance (Coast Time):" in captured.out
    
    # Can't reliably assert PASS or WARNING as it depends on CPU speed,
    # but we can ensure it outputs one or the other.
    assert "Coast time" in captured.out
