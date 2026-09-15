import subprocess
import time
import sys
from pathlib import Path

# Start server
server_proc = subprocess.Popen(["python3", "-m", "social_platform.api.server"])
time.sleep(1) # wait for boot

try:
    from social_platform.client.client import SocialPlatformClient
    client = SocialPlatformClient("http://localhost:8080")
    
    # Test registry
    blocks = client.get_genesis_registry()
    print("Initial registry keys:", list(blocks.keys())[:3])
    
    # Test reserve
    res = client.reserve_genesis_block("TestCorp", "http://logo")
    print("Reserve result:", res)
    
    # Check registry again
    blocks_after = client.get_genesis_registry()
    print("Registry after (Block 1):", blocks_after.get("1"))
    
    if res.get("status") != "success":
        print("FAIL: status not success")
        sys.exit(1)
        
finally:
    server_proc.terminate()
    server_proc.wait()
    
print("Frontend/Backend integration verified successfully!")
