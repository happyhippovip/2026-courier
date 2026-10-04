import time
import threading
import math

def simulate_escrow_coast(coast_threshold_ms=50.0):
    print("Simulating Escrow Bypass / Coast Time Test (RUN9)...")
    stop_signal = threading.Event()
    
    # Variable to track actual stopping time
    stopping_distance_ns = [0]
    
    def engine_thread():
        while not stop_signal.is_set():
            # simulate heavy load
            _ = [math.sqrt(i) for i in range(1000)]
        # Record time when thread actually acknowledges stop
        stopping_distance_ns[0] = time.perf_counter_ns()
            
    t = threading.Thread(target=engine_thread)
    t.start()
    
    # Let it run
    time.sleep(1)
    
    # Send stop signal and record timestamp
    signal_time = time.perf_counter_ns()
    stop_signal.set()
    
    t.join()
    
    coast_time_ms = (stopping_distance_ns[0] - signal_time) / 1_000_000.0
    print(f"Signal sent at: {signal_time} ns")
    print(f"Engine stopped at: {stopping_distance_ns[0]} ns")
    print(f"Physical stopping distance (Coast Time): {coast_time_ms:.4f} ms")
    
    if coast_time_ms > coast_threshold_ms:
        print(f"WARNING: Coast time exceeds {coast_threshold_ms}ms limit!")
    else:
        print(f"PASS: Coast time is within {coast_threshold_ms}ms limit.")

if __name__ == '__main__':
    simulate_escrow_coast()
