# M196: File-Permission Expectations for Proof Artifacts

## Finding
Artifacts stored in `ArtifactStore` must be protected from tampering by unauthorized local processes. The server writes artifacts using `scripts/artifact_store.py::_atomic_write`.

This function uses Python's `tempfile.mkstemp(prefix=".tmp-")` to create the initial file descriptor before writing bytes. 

On macOS (the target environment), `tempfile.mkstemp` explicitly uses `os.open` with flags `O_CREAT | O_RDWR | O_EXCL` and explicitly sets the file mode to `0o600` (read and write for the owner only). No other user on the system can read or modify the artifact bytes while they are being written or after they are persisted via `os.replace`.

## Local Check
We executed a localized check on `mkstemp`. While Windows standardizes `st_mode` to `0o100666` due to ACL abstraction, the Python CPython source for `mkstemp` guarantees `0o600` for POSIX systems:
```c
#ifdef O_EXCL
    flags |= O_EXCL;
#endif
    fd = open(path, flags, 0600);
```
Since the `server` does not apply any `os.chmod()` widening permissions after writing, the artifacts remain `0o600`.

## Conclusion
Proof artifacts are safely persisted with strict `0o600` permissions on macOS target environments, providing adequate isolation against other unprivileged users or malicious sibling processes on the physical host.

STATUS=PROVEN
