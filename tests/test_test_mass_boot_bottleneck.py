import runpy
from pathlib import Path
from unittest.mock import patch

def test_hashing_speed_mocked(capsys):
    script_path = Path(__file__).parent.parent / "scripts" / "test_mass_boot_bottleneck.py"
    
    # We patch time.time to avoid relying on actual elapsed time which could be 0,
    # causing a ZeroDivisionError in throughput calculation if it runs too fast under mock.
    with patch("scripts.test_mass_boot_bottleneck.time.time") as mock_time:
        # Mock os.urandom to return a tiny payload so hashing is instant
        with patch("scripts.test_mass_boot_bottleneck.os.urandom", return_value=b"A"):
            mock_time.side_effect = [0.0, 1.0] # start_time=0, end_time=1
            runpy.run_path(str(script_path), run_name="__main__")
            
    captured = capsys.readouterr()
    assert "Starting hash of 5GB in-memory simulation..." in captured.out
    assert "Throughput: 5000.00 MB/s" in captured.out
