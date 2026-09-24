import time
import sys
from pathlib import Path
from scripts.windows_muse_wall.supervisor import MuseWallSupervisor

def soak_test():
    print("Starting soak test...")
    root = Path(__file__).parent.parent.parent
    sup = MuseWallSupervisor(root)
    sup.initialize()
    
    # Enable launch
    sup.config["provider_launch_enabled"] = True
    
    # 1. Start a few slots
    slots_to_start = ["MUSE-01", "MUSE-02", "MUSE-03"]
    for sid in slots_to_start:
        res = sup.start_slot(sid, [sys.executable, "-c", "import time; time.sleep(10)"])
        print(f"Start {sid}: {res['started']}")
        
    time.sleep(2)
    
    # 2. Stop one
    print("Stopping MUSE-02")
    sup.stop_slot("MUSE-02")
    
    # 3. Simulate supervisor restart
    print("Restarting supervisor")
    sup2 = MuseWallSupervisor(root)
    sup2.config["provider_launch_enabled"] = True
    sup2.initialize()
    
    for sid in slots_to_start:
        sup2.reconcile_slot(sid)
        
    status = sup2.status()
    print("Status after restart:", status)
    
    # 4. Stop remaining
    for sid in slots_to_start:
        if sid != "MUSE-02":
            sup2.stop_slot(sid)
            
    print("Soak test completed successfully.")

if __name__ == "__main__":
    soak_test()
