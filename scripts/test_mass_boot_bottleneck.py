import time
import hashlib
import os
import tempfile

def test_hashing_speed():
    # Simulate a 5GB file without actually writing 5GB to disk to save time/space
    # We'll hash a smaller block repeatedly
    chunk_size = 1024 * 1024 * 10  # 10 MB
    num_chunks = 500  # 500 * 10 MB = 5 GB
    
    chunk = os.urandom(chunk_size)
    h = hashlib.sha256()
    
    print("Starting hash of 5GB in-memory simulation...")
    start_time = time.time()
    
    for i in range(num_chunks):
        h.update(chunk)
        if i % 100 == 0:
            print(f"Processed {i * 10} MB...")
            
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Hash: {h.hexdigest()}")
    print(f"Time taken to hash 5GB: {duration:.2f} seconds")
    print(f"Throughput: {5000 / duration:.2f} MB/s")

if __name__ == '__main__':
    test_hashing_speed()
