import json
import os
import hashlib
from pathlib import Path

def test():
    test_dir = Path("/Users/user/Downloads/2026-courier/coordination")
    test_file = test_dir / "test_atomic.json"
    tmp_file = test_file.with_suffix(".tmp")
    
    data = {"test": "data"}
    with open(tmp_file, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
        
    os.replace(tmp_file, test_file)
    
    with open(test_file, "r") as f:
        read_data = f.read()
    
    h = hashlib.sha256(read_data.encode("utf-8")).hexdigest()
    expected = hashlib.sha256('{"test": "data"}'.encode("utf-8")).hexdigest()
    
    if h == expected:
        print("ATOMIC_WRITE_TEST = PASS")
    else:
        print("ATOMIC_WRITE_TEST = FAIL")
        
    os.remove(test_file)

if __name__ == "__main__":
    test()
