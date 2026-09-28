# MAC-FINISH-03 — Filesystem Isolation Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-03
- **Area**: FILESYSTEM_ISOLATION_PACKET
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Status**: COMPLETE

This packet defines directory hierarchies, permissions, atomic file operations, and ownership rules to ensure complete filesystem isolation during staging runs.

---

## 2. Directory Hierarchy
```
/Users/user/Downloads/2026-courier/
├── server/
│   └── state/
│       ├── isolated_run1/           # RUN_1 isolated state
│       │   ├── central_state.json   # RUN_1 coordinator state
│       │   └── artifacts/           # RUN_1 uploaded artifacts
│       └── isolated_run2/           # RUN_2 restart isolated state
│           ├── central_state.json   # RUN_2 coordinator state
│           └── artifacts/           # RUN_2 uploaded artifacts
└── logs/
    ├── run1_server.log
    ├── run1_worker.log
    ├── run1_verifier.log
    ├── run2_server_p1.log
    └── run2_server_p2.log
```

---

## 3. Atomic Write Semantics
To prevent reading half-written or corrupted state:
1. Write payload to temporary file: `{path}.tmp.{pid}`
2. Flush and synchronize buffer to disk: `f.flush(); os.fsync(f.fileno())`
3. Execute atomic replace: `os.replace(temp_path, final_path)`

---

## 4. Cleanup & Quarantine Policies
- **Pre-Flight Purge**: Prior to launch, `isolated_run1` or `isolated_run2` must be purged if marked stale.
- **Quarantine on Error**: If a run fails, the directory is immediately renamed to `server/state/quarantine_{run_id}_{timestamp}` to preserve forensic evidence without contaminating new runs.
