# M187 — macOS Temp Directory Isolation vs In-Tree State Path Verification

## 1. Overview & Authority
- **Task ID**: M187
- **Area**: FS_ISOLATION
- **Status**: COMPLETE

## 2. Isolation Topology
- Avoid `/tmp` and `/var/folders` for persistent test state to eliminate race conditions with OS cleaners.
- In-tree isolated directory: `server/state/isolated_run1/` and `server/state/isolated_run2/`.
- Cross-run boundary: State directories are strictly partitioned by run identifier.
