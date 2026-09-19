import threading, time

STATE_LOCK = threading.RLock()
NEW_TASK_EVENT = threading.Condition(STATE_LOCK)

def worker():
    with NEW_TASK_EVENT:
        NEW_TASK_EVENT.wait(timeout=1)
        print("Done wait")

t = threading.Thread(target=worker)
t.start()
t.join()
