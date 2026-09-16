# PATCH SPECIFICATION — CANDIDATE L01: HIERARCHICAL & SEMANTIC RESOURCE LOCKING

- **Invariant**:
  $$\forall R_1, R_2 \in \text{DeclaredResources}: \text{Conflicts}(R_1, R_2) \implies \text{CONCURRENT\_MUTEX\_BLOCKED}$$
  $$\forall R_1, R_2 \in \text{DeclaredResources}: \neg \text{Conflicts}(R_1, R_2) \implies \text{PARALLEL\_EXECUTION\_PERMITTED}$$
- **Severity**: P0 (Corrupted repositories, clobbered source trees, deadlocks)
- **Target Subsystem**: `supervisor/no_stacking.js` & `supervisor/lease_manager.js`

---

## 1. CURRENT BEHAVIOR
In the existing codebase:
- `supervisor/no_stacking.js` implements `NoStackingDetector.evaluateHeavyTaskSubmission()`.
- It evaluates collisions by matching `if (lease.task_id === task_id)`.
- It computes a signature of `task_id + work_category + command`.
- **THE FLAW**:
  1. If two distinct tasks ($T_1 \neq T_2$) execute concurrently and mutate the same files, directories, ports, or databases, `no_stacking.js` ignores them entirely because `lease.task_id !== task_id`.
  2. If tasks declare file scopes, traditional equality (`scopeA === scopeB`) misses parent/child directory collisions (`src/` vs `src/core/auth/`).
  3. Case sensitivity is ignored: `src/Core/` and `src/core/` are treated as distinct strings, escaping mutex on case-insensitive filesystems (Windows NTFS, macOS default APFS).
  4. Non-filesystem resources (database tables, network ports, git refs) have no formal collision model.

---

## 2. TARGET BEHAVIOR
- Tasks declare write scopes using a canonical URI scheme:
  - `tree:<canonical-relative-path>/`: Directory tree lock (locks directory and all descendants).
  - `file:<canonical-relative-path>`: Single file lock (locks file and conflicts with any enclosing `tree:`).
  - `db:<database-name>/<table-name>`: Database table lock.
  - `port:<tcp-or-udp>/<port-number>`: Local network port binding lock.
  - `gitref:<ref-name>`: Git reference lock (e.g. `gitref:refs/heads/main`).
  - `artifact:<artifact-id>`: Artifact production lock.
- **Mutual Exclusion**:
  - Two active tasks whose declared write resources intersect or hierarchically overlap CANNOT execute concurrently on the same target host/repository.
  - One task acquires the lease; the second task transitions to `BLOCKED_RESOURCE_LOCK` (or queued until release).
- **Concurrency Freedom**:
  - Unrelated writers (e.g. `tree:src/moduleA/` and `tree:src/moduleB/`) MUST NOT be globally serialized and execute concurrently in full parallelism.

---

## 3. PLATFORM & PATH SEMANTICS SPECIFICATION
1. **Repository Root Binding**:
   - All filesystem resources are bound and resolved relative to canonical repository root. Absolute paths outside repository are rejected unless explicitly declared under `external:`.
2. **Path Normalization**:
   - Convert all backslashes `\` to forward slashes `/`.
   - Resolve `.` and `..` segments before evaluation.
   - Strip duplicate slashes `//`.
   - For `tree:`, ensure a mandatory trailing slash `/`.
3. **Case Sensitivity Handling**:
   - Windows NTFS: Case-preserving, case-insensitive -> Fold to lowercase (`toLowerCase()`).
   - macOS APFS: Default case-preserving, case-insensitive -> Fold to lowercase (`toLowerCase()`).
   - Linux / APFS case-sensitive volume: Preserved exact case.
   - **Runtime Derivation Rule**: The lock engine queries `isFilesystemCaseInsensitive(rootPath)` at initialization rather than hard-coding OS assumptions. If uncertain, it defaults to case-insensitive (fail-closed against collision).
4. **Symlink Ambiguity**:
   - If symlinks exist, paths must be resolved via `fs.realpathSync` to canonical physical paths before prefix comparison.

---

## 4. MINIMAL CHANGE SPECIFICATION
In `supervisor/resource_lock_manager.js` (replacing naive `no_stacking.js` logic):

```javascript
class ResourceLockManager {
  constructor(isCaseInsensitive = true) {
    this.isCaseInsensitive = isCaseInsensitive;
    this.activeLocks = new Map(); // resourceKey -> { taskId, leaseId, mode: 'WRITE' }
  }

  canonicalizeResource(rawUri) {
    if (!rawUri || typeof rawUri !== 'string') {
      throw new Error('[RESOURCE_LOCK_ERROR] Valid resource URI required');
    }

    const colonIdx = rawUri.indexOf(':');
    if (colonIdx === -1) {
      // Default to tree if bare directory
      return this.canonicalizeResource(`tree:${rawUri}`);
    }

    const scheme = rawUri.slice(0, colonIdx).toLowerCase();
    let val = rawUri.slice(colonIdx + 1);

    if (scheme === 'tree' || scheme === 'file') {
      val = path.normalize(val).replace(/\\/g, '/');
      if (scheme === 'tree' && !val.endsWith('/')) {
        val += '/';
      }
      if (this.isCaseInsensitive) {
        val = val.toLowerCase();
      }
      return `${scheme}:${val}`;
    }

    if (scheme === 'port' || scheme === 'db' || scheme === 'gitref' || scheme === 'artifact') {
      return `${scheme}:${val.trim().toLowerCase()}`;
    }

    throw new Error(`[RESOURCE_LOCK_ERROR] Unsupported resource scheme: ${scheme}`);
  }

  static checkConflict(resA, resB) {
    if (resA === resB) return true;

    const [schemeA, pathA] = [resA.slice(0, resA.indexOf(':')), resA.slice(resA.indexOf(':') + 1)];
    const [schemeB, pathB] = [resB.slice(0, resB.indexOf(':')), resB.slice(resB.indexOf(':') + 1)];

    if (schemeA !== schemeB) {
      // Cross-scheme: file vs tree
      if (schemeA === 'file' && schemeB === 'tree') {
        return pathA.startsWith(pathB); // e.g. file:src/a.js inside tree:src/
      }
      if (schemeA === 'tree' && schemeB === 'file') {
        return pathB.startsWith(pathA);
      }
      return false;
    }

    // Same scheme
    if (schemeA === 'tree') {
      return pathA.startsWith(pathB) || pathB.startsWith(pathA);
    }

    if (schemeA === 'file' || schemeA === 'port' || schemeA === 'db' || schemeA === 'gitref') {
      return pathA === pathB;
    }

    return false;
  }

  acquireLocks(taskId, leaseId, declaredResources = []) {
    const canonical = declaredResources.map(r => this.canonicalizeResource(r));

    // 1. Check conflicts against all currently active locks
    for (const res of canonical) {
      for (const [activeRes, lock] of this.activeLocks.entries()) {
        if (lock.taskId === taskId) continue; // Same task re-entrancy allowed
        if (ResourceLockManager.checkConflict(res, activeRes)) {
          return {
            acquired: false,
            conflicting_resource: activeRes,
            conflicting_task_id: lock.taskId,
            conflicting_lease_id: lock.leaseId,
            reason: `Resource conflict: '${res}' conflicts with active lock '${activeRes}' held by task '${lock.taskId}'`
          };
        }
      }
    }

    // 2. Grant all locks atomically
    for (const res of canonical) {
      this.activeLocks.set(res, { taskId, leaseId, mode: 'WRITE', acquiredAt: new Date().toISOString() });
    }

    return { acquired: true, granted_resources: canonical };
  }

  releaseLocksForLease(leaseId) {
    const released = [];
    for (const [res, lock] of this.activeLocks.entries()) {
      if (lock.leaseId === leaseId) {
        this.activeLocks.delete(res);
        released.push(res);
      }
    }
    return released;
  }
}
```

---

## 5. REQUIRED STATE FIELDS & PERSISTENCE
- In `ProcessLease` (`supervisor/lease_manager.js`):
  - `declared_resources`: `Array<string>` (e.g. `['tree:src/core/', 'port:tcp/8080']`)
  - `acquired_locks`: `Array<string>`
  - `lock_state`: `'GRANTED'` | `'WAITING'` | `'RELEASED'`
- Persistence: Stored durably inside `leases.json`. Leases in `WAITING` cannot spawn processes.

---

## 6. FAIL-CLOSED RULES
- If a task declares NO resources, but is classified as `MUTATIVE_WORKER`, it defaults to locking `tree:/` (repository-wide lock, single writer safe mode) until explicit scopes are declared.
- If path normalization encounters unresolvable symlinks, fail closed and refuse lease.

---

## 7. MIGRATION & ROLLBACK
- **Migration**: Legacy active tasks without declared resources are assigned `declared_resources: ['legacy:unspecified_scope']`. Unspecified legacy tasks run sequentially against other unspecified tasks, but do not block modern explicitly scoped tasks unless path collision is suspected.
- **Rollback**: If reverted to naive string match, old leases retain their array without breakage.

---

## 8. CLASSIFICATION
- **Classification**: `LIKELY_PRODUCTION_DEFECT` (P0).
- **Mac-Native Proof**: None required. Pure path & URI logic.
