import time
import statistics
import sys

def measure_jitter(duration_sec=10, interval_sec=0.01):
    print(f"Starting timing-jitter measurement for {duration_sec}s with {interval_sec}s intervals...")

    # Warm up before the window starts. On Windows a requested 1ms sleep can
    # take much longer, and that used to consume a short measurement entirely.
    for _ in range(100):
        time.sleep(0.001)

    delays = []
    end_time = time.perf_counter() + max(0.0, duration_sec)
    while True:
        start = time.perf_counter_ns()
        time.sleep(interval_sec)
        actual_delay = time.perf_counter_ns() - start
        delays.append(actual_delay / 1_000_000.0)
        # Two samples are required for a standard deviation.
        if len(delays) >= 2 and time.perf_counter() >= end_time:
            break

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
