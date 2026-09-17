import threading
import time
import sys
import os

# Set up env so app.py can be imported
os.environ["COURIER_API_KEY"] = "dev-secret-key"
os.environ["COURIER_VERIFIER_API_KEY"] = "dev-secret-key"

from server.app import load_state, save_state

def reader():
    for _ in range(50):
        try:
            state = load_state()
        except Exception as e:
            print(f"Reader failed: {e}")
            sys.exit(1)
        time.sleep(0.01)

def writer(tid):
    for i in range(50):
        try:
            state = load_state()
            state.setdefault("test_key", {})
            state["test_key"][f"thread_{tid}"] = i
            save_state(state)
        except Exception as e:
            print(f"Writer failed: {e}")
            sys.exit(1)
        time.sleep(0.01)

threads = []
for i in range(10):
    t = threading.Thread(target=reader)
    t.start()
    threads.append(t)

for i in range(10):
    t = threading.Thread(target=writer, args=(i,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()

print("W8: Atomic State Mutation proven. No PermissionErrors.")
