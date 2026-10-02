import time
import math

def thermal_stress_test(iterations=5):
    print(f"Starting Thermal/Clock Stress Test (RUN18) with {iterations} iterations...")
    
    results = []
    
    for i in range(iterations):
        start = time.perf_counter()
        
        # CPU intensive work
        # Generating a large list of primes or math operations
        c = 0
        for x in range(1, 5_000_000):
            c += (x * 2.5) / 1.1
            
        duration = time.perf_counter() - start
        results.append(duration)
        print(f"Iteration {i+1}: {duration:.4f} seconds")
        
    diff = max(results) - min(results)
    print(f"Max variation between iterations: {diff:.4f} seconds")
    
    if diff > 0.5:
        print("WARNING: High variation detected. Possible P-state changes or thermal throttling.")
    else:
        print("PASS: Execution times are stable across iterations.")

if __name__ == '__main__':
    thermal_stress_test()
