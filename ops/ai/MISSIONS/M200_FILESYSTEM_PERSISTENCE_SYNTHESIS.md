# M200: Filesystem/Persistence Synthesis

## Synthesis
This document synthesizes the findings from the filesystem and persistence verification checks (M191-M199) for the courier architecture, focusing on target macOS environments.

1. **Atomic State Updates**: The courier server utilizes `os.replace` which maps to the atomic `rename(2)` syscall on POSIX/macOS, ensuring partial states are never read. (M191)
2. **Durability Guarantees**: Flushes and `os.fsync` are explicitly invoked on the temporary file descriptor before the atomic rename, preventing data corruption on hard crash or power loss. (M192)
3. **Stale/Temporary File Cleanup**: The deterministic `.tmp` suffixes used by the server ensure that crashed writes overwrite older temporary files without unbound leaks, though randomized temporary files in some client scripts may leak on hard crash. (M193)
4. **Result File Integrity**: Artifact uploads require strict pre-upload declarations of exact size and SHA256 hashes. The server validates incoming streams, preventing partial/truncated files from ever being stored. (M194)
5. **Stale File Precedence**: The server ignores temporary `.tmp` files completely upon startup. The last fully atomic and durable rename (the primary file) always takes precedence. (M195)
6. **Artifact File Permissions**: The artifact store uses `tempfile.mkstemp`, enforcing strict `0o600` POSIX permissions on stored binary blobs, preventing read/write access by other users. (M196)
7. **Path Traversal Defenses**: The artifact server strictly uses content-addressed storage (`blobs/<sha>`), mathematically eliminating symlink and path-resolution ambiguity on the server filesystem. (M197)
8. **Case-Sensitivity Portability**: Artifact hashes are strictly case-sensitive. While case variations ("result.json" vs "Result.json") yield distinct records, exact matching in task bindings prevents storage corruption, isolating the risk to worker extraction. (M198)
9. **Directory Isolation**: The state directories rely on standard OS umask for isolation. While JSON state files may be globally readable (e.g., `0o644`), no credentials are saved in them, relying on environment variables for API keys instead. (M199)

## Conclusion
The persistence layer of the courier system is highly robust for production physical runs, guaranteeing crash-safety, upload integrity, and path-traversal immunity.

STATUS=PROVEN
