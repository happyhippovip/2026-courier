import runpy
from pathlib import Path
import scripts.test_thermal_stress_run18 as thermal_module
from unittest.mock import patch

def test_thermal_stress_fast(capsys):
    # We can mock the inner loop range to be much smaller using patch on builtins? 
    # Actually, we can just patch time.perf_counter and return synthetic times.
    with patch("scripts.test_thermal_stress_run18.time.perf_counter") as mock_perf:
        # 5 iterations require 10 calls to perf_counter (start and end per iter)
        mock_perf.side_effect = [
            0.0, 0.1,  # iter 1: 0.1s
            0.1, 0.2,  # iter 2: 0.1s
            0.2, 0.3,  # iter 3: 0.1s
            0.3, 0.4,  # iter 4: 0.1s
            0.4, 0.5   # iter 5: 0.1s
        ]
        
        thermal_module.thermal_stress_test(iterations=5)
        
    captured = capsys.readouterr()
    assert "Starting Thermal/Clock Stress Test (RUN18)" in captured.out
    assert "Max variation between iterations" in captured.out
    assert "PASS: Execution times are stable across iterations" in captured.out

def test_thermal_stress_warning(capsys):
    with patch("scripts.test_thermal_stress_run18.time.perf_counter") as mock_perf:
        mock_perf.side_effect = [
            0.0, 0.1,  # iter 1: 0.1s
            0.1, 1.0,  # iter 2: 0.9s (huge variation!)
            1.0, 1.1,  # iter 3: 0.1s
        ]
        thermal_module.thermal_stress_test(iterations=3)
        
    captured = capsys.readouterr()
    assert "WARNING: High variation detected" in captured.out

def test_thermal_stress_main(capsys):
    script_path = Path(__file__).parent.parent / "scripts" / "test_thermal_stress_run18.py"
    
    # Run the script via runpy natively
    runpy.run_path(str(script_path), run_name="__main__")
    
    captured = capsys.readouterr()
    assert "Starting Thermal/Clock Stress Test (RUN18) with 5 iterations..." in captured.out
