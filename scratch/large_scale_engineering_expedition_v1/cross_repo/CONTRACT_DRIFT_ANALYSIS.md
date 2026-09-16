# CROSS-REPOSITORY CONTRACT DRIFT ANALYSIS

**Expedition**: `WINDOWS_COURIER_LARGE_SCALE_ENGINEERING_EXPEDITION_V1`  
**Source Repos**: `courier/` vs `project-memory/`  
**Evaluation Date**: 2026-09-10T04:24:31.225Z

---

## 1. Executive Summary

A comprehensive architectural audit between the active **Courier** repository and the canonical **2026-Project-Memory** repository revealed critical contract differences that historically caused cross-machine friction:

1. **Lease & Concurrency Semantics**:
   - Production Courier (`courier/supervisor/no_stacking.js`) checks only exact task ID match, failing to prevent parent/child path overlaps.
   - Project-Memory (`project-memory/parallel_writer/lease_manager.js`) implements deterministic path prefix checking, TTL expiration, and fencing tokens.
   - **Resolution**: `ShadowCourierKernelV2` integrates the deterministic prefix containment and fencing token model, preventing race collisions.

2. **Host Role Partitioning**:
   - Project-Memory explicitly documents host truth in `PROJECT_STATE.md` and `company_os/device_truth.json`:
     - **PC2 (Windows 10)**: Designated as `MEMORY_RIGHT_ARM` for continuous research, offline engineering, differential testing, and heavy compute.
     - **Rechner 1 (Mac)**: Designated as `PRODUCT_SINGLE_WRITER` for `universuX`, Courier core git modifications, and production signing.
   - **Resolution**: Expedition strictly enforces this invariant. Zero touches to universuX, zero Mac SSH/remote commands, zero financial liability execution on Windows.

3. **Schema Normalization**:
   - Field names and task lifecycle states differed across the repos.
   - A universal bi-directional normalization adapter has been indexed in `SCHEMA_NORMALIZATION_MAP.json`.

---

## 2. Detailed Contract Matrix

| Contract Dimension | Courier Legacy | Project-Memory | Shadow Kernel V2 | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Task State** | STAGED, DISPATCHED, COMPLETED | INBOX, QUEUED, IN_PROGRESS, DONE | Standardized 5-State Machine | Mapped |
| **Lease Collision** | Blind to subpaths | Prefix overlap containment | Hierarchical NTFS containment | Aligned |
| **Fencing Tokens** | None | Monotonic integer tokens | Cryptographic tokens | Unified |
| **Host Confinement** | Uncoordinated | Mac Single-Writer / Win Worker | Strict OS Confinement Gate | Enforced |
| **Authority Ceiling**| None | spend_safety checks | 7-Level Capability Lattice | Unified |

