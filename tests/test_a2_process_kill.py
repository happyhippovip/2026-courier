import os
import subprocess
import time
import pytest
import sys

def test_no_foreign_pkill():
    # Start dummy processes that match the pkill patterns but are NOT owned by the scripts
    dummy_symphony = subprocess.Popen(["python3", "-c", "import time; time.sleep(10)", "Courier Symphony Test"])
    dummy_health = subprocess.Popen(["python3", "-c", "import time; time.sleep(10)", "courier_verifier.py"])

    time.sleep(1) # Let them start
    assert dummy_symphony.poll() is None
    assert dummy_health.poll() is None

    # Run the offending scripts
    subprocess.run(["bash", "scripts/sync_test_mac.sh"], env=os.environ, cwd=".")
    subprocess.run(["bash", "scripts/local_health_watchdog.sh"], env=os.environ, cwd=".")
    
    # Check if dummies survived
    time.sleep(1)
    symphony_alive = dummy_symphony.poll() is None
    health_alive = dummy_health.poll() is None
    
    # Cleanup if still alive
    if symphony_alive:
        dummy_symphony.terminate()
    if health_alive:
        dummy_health.terminate()

    assert symphony_alive, "sync_test_mac.sh killed a foreign process!"
    assert health_alive, "local_health_watchdog.sh killed a foreign process!"
