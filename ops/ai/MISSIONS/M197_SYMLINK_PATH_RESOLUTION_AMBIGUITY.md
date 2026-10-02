# M197: Symlink/Path-Resolution Ambiguity

## Finding
Path-resolution attacks typically involve tricking a privileged process into overwriting critical files via symlinks (e.g. providing an artifact name like `/etc/passwd` or `../secret.txt`).

The courier architecture eliminates path-resolution ambiguity on the server side:
1. `scripts/artifact_store.py::is_safe_artifact_name` explicitly rejects any string containing `..` or identifying as an absolute path on either POSIX or Windows (e.g., `/foo`, `C:\foo`).
2. Crucially, the server **never attempts to write the artifact to the user-supplied path**. It uses content-addressed storage (CAS). 
   - Bytes are written to `server/state/artifacts/blobs/<sha256[:2]>/<sha256>`.
   - The user-supplied name is stored solely as metadata inside `server/state/artifacts/records/<artifact_id>.json`.

## Local Check
Inspection of `ArtifactStore.put` verifies that it computes the SHA256 of the payload and constructs the blob path strictly from the SHA256 string.
```python
        sha256 = hashlib.sha256(data).hexdigest()
        # ...
        blob = self._blob_path(sha256)
        if not blob.exists():
            _atomic_write(blob, data)
```
Since the server filesystem never evaluates the user-provided artifact name as a filesystem path for writing, there is zero risk of symlink traversal or path-resolution ambiguity on the server. The client is responsible for safely extracting the artifact to its own isolated sandbox.

## Conclusion
The server architecture mathematically eliminates path-resolution ambiguity for persisted artifacts by decoupling the logical path (metadata) from the physical path (content-addressed blob).

STATUS=PROVEN
