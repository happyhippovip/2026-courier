import os
import sys
import json
import time
import uuid
import tracemalloc

# Make sure we can import from server
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server.app import load_state, save_state

def run_mass_import(record_count=10000):
    print(f"Starting local import of {record_count} synthetic records...")
    
    # 1. Start memory tracing
    tracemalloc.start()
    start_time = time.time()
    
    # 2. Generate synthetic data
    print("Generating synthetic tasks...")
    new_tasks = {}
    for i in range(record_count):
        tid = f"task-import-{uuid.uuid4().hex[:8]}-{i}"
        new_tasks[tid] = {
            "task_id": tid,
            "import_id": f"IMP-{uuid.uuid4().hex[:8]}",
            "external_id": f"EXT-{i}",
            "status": "QUEUED",
            "payload": {
                "action": "synthetic_work",
                "data": "x" * 512  # Simulate some payload size (~512 bytes)
            },
            "created_at": time.time()
        }
        
    generation_time = time.time()
    
    # 3. Load State
    print("Loading central state...")
    state = load_state()
    if "tasks" not in state:
        state["tasks"] = {}
        
    initial_count = len(state["tasks"])
    
    # 4. Merge Data
    print("Merging tasks into state...")
    state["tasks"].update(new_tasks)
    
    # 5. Save State
    print("Saving central state...")
    save_state(state)
    
    end_time = time.time()
    
    # 6. Stop memory tracing and get metrics
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    duration = end_time - start_time
    final_count = len(state["tasks"])
    added_count = final_count - initial_count
    
    print("\n" + "="*40)
    print("IMPORT METRICS")
    print("="*40)
    print(f"Target Import Count : {record_count}")
    print(f"Actually Added      : {added_count}")
    print(f"Total State Tasks   : {final_count}")
    print(f"Generation Time     : {generation_time - start_time:.4f} seconds")
    print(f"Total Import Time   : {duration:.4f} seconds")
    print(f"Peak Memory Usage   : {peak_mem / (1024*1024):.2f} MB")
    print("="*40)

if __name__ == "__main__":
    count = 10000
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    run_mass_import(count)
