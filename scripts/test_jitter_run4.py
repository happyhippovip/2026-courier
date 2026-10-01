import time
import statistics
import sys

def measure_jitter(duration_sec=10, interval_sec=0.01):
    print(f"Starting timing-jitter measurement for {duration_sec}s with {interval_sec}s intervals...")
    
    delays = []
    end_time = time.time() + duration_sec
    
    # Warmup
    for _ in range(100):
        time.sleep(0.001)
        
    while time.time() < end_time:
        start = time.perf_counter_ns()
        time.sleep(interval_sec)
        actual_delay = time.perf_counter_ns() - start
        
        # Convert to milliseconds
        delays.append(actual_delay / 1_000_000.0)
        
    expected_ms = interval_sec * 1000
    deviations = [abs(d - expected_ms) for d in delays]
    
    print(f"Measured {len(delays)} intervals.")
    print(f"Expected interval: {expected_ms:.3f} ms")
    print(f"Average actual interval: {statistics.mean(delays):.3f} ms")
    print(f"Max jitter (deviation): {max(deviations):.3f} ms")
    print(f"Jitter standard deviation: {statistics.stdev(delays):.3f} ms")
    
if __name__ == '__main__':
    # Defaulting to 10s for simulation, intended for 48h (172800s) on real hardware
    measure_jitter()
