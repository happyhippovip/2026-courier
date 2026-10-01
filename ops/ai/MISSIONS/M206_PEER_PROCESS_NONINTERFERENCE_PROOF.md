# M206: Peer-Process Noninterference Proof

## Goal
Prove that concurrent executions (peer processes) of the Courier suite on the same physical host cannot interfere with each other or silently corrupt each other's state.

## Mechanism

### 1. Host-Level Global Mutex via TCP Port
The most significant defense against peer-process interference is the static assignment of TCP Port 8080 for `server.app`.
Because the execution scripts (`run_1_mac.sh`, `run_2_mac.sh`) rigidly require binding to `8080`, and the OS TCP/IP stack prevents multiple independent process groups from binding to the same port on the same interface concurrently, **only one instance of Courier can be active on a host at any given time**.

If a second job attempts to start while the first is running, the `lsof -i :8080` preflight check will detect the listening port and immediately abort the second job. Even if the preflight is bypassed, the subsequent `Flask.run()` call will crash with a socket bind error.

### 2. File-Level Mutexes and Control Locks
The `runtime_state.py` leverages `fcntl.flock` on `central_state.json.lock` (or equivalent lock files) for atomic filesystem modifications. 
```python
@contextmanager
def control_lock(path):
    lock_file = Path(path).with_suffix('.lock')
    with open(lock_file, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```
If two processes somehow share a workspace, the POSIX file locks ensure that state reads/writes remain mutually exclusive and atomic.

### 3. Artifact Naming and Collision Avoidance
Artifact storage uses CAS (Content-Addressable Storage) based on SHA-256 hashes of the file contents. If two peer processes produce the exact same file, the hash is identical, and overwriting it is idempotent. If they produce different files, the hashes diverge, preventing one process from accidentally truncating or corrupting a file expected by another.

## Conclusion
The combination of a strict global network mutex (Port 8080) and file-level `flock` ensures that peer-process interference is impossible. The system fails fast (aborting the second run) rather than attempting to multiplex or share resources, preserving the exact reproducibility of the test environment.
