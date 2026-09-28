# M191 — Artifact Storage Path Schema & Directory Hierarchy Layout

## 1. Overview & Authority
- **Task ID**: M191
- **Area**: ARTIFACT_SCHEMA
- **Status**: COMPLETE

## 2. Directory Schema
```
server/state/isolated_run1/
  ├── artifacts/
  │   └── <task_id>/
  │       └── artifact.bin
  ├── database.sqlite
  └── staging.pid
```
Hierarchy guarantees non-colliding task artifact namespaces.
