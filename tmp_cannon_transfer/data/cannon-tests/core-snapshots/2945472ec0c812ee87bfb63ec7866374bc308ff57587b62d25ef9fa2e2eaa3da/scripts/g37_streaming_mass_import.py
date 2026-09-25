import os
import sys
import json
import time
import uuid
import argparse
import tracemalloc

def generate_tasks_stream(count):
    """Generator that yields synthetic tasks one by one."""
    for i in range(count):
        tid = f"task-import-{uuid.uuid4().hex[:8]}-{i}"
        yield {
            "task_id": tid,
            "import_id": f"IMP-{uuid.uuid4().hex[:8]}",
            "external_id": f"EXT-{i}",
            "status": "QUEUED",
            "payload": {
                "action": "synthetic_work",
                "data": "x" * 256  # Moderate payload
            },
            "created_at": time.time()
        }

def run_streaming_import(count, target_file):
    print(f"Starting STREAMING mass import of {count} records...")
    
    tracemalloc.start()
    start_time = time.time()
    
    # We simulate a streaming ingest by writing directly to an append-only JSONL file 
    # (or a streaming JSON writer) to keep peak memory virtually zero during generation.
    # If the system were to consume it, it would read line-by-line.
    
    # We will write to a JSON Lines file to prove streaming capability
    written_count = 0
    with open(target_file, "w", encoding="utf-8") as f:
        for task in generate_tasks_stream(count):
            f.write(json.dumps(task) + "\n")
            written_count += 1
            if written_count % 100000 == 0:
                print(f"  ... {written_count} / {count} records streamed to disk.")
                
    end_time = time.time()
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    duration = end_time - start_time
    file_size_mb = os.path.getsize(target_file) / (1024 * 1024)
    
    print("\n" + "="*45)
    print("STREAMING IMPORT METRICS (GENERATION & I/O)")
    print("="*45)
    print(f"Target Count        : {count}")
    print(f"Records Streamed    : {written_count}")
    print(f"Total Time          : {duration:.4f} seconds")
    print(f"Throughput          : {written_count / duration:.0f} records / sec")
    print(f"Peak Memory Usage   : {peak_mem / (1024*1024):.4f} MB")
    print(f"Output File Size    : {file_size_mb:.2f} MB")
    print("="*45)
    print(f"Test data written to: {target_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="G37 Streaming Mass Import Generator")
    parser.add_argument("--count", type=int, default=100000, help="Number of records to generate")
    parser.add_argument("--output", type=str, default="streaming_import_payload.jsonl", help="Output JSONL file")
    args = parser.parse_args()
    
    run_streaming_import(args.count, args.output)
