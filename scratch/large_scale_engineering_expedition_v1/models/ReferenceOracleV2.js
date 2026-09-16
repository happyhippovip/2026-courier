// Independent Reference Oracle V2 — Expedition V1
// Independent decision specification for differential state validation.

const crypto = require('crypto');
const path = require('path');

class ReferenceOracleV2 {
  constructor() {
    this.dispatchedTasks = new Map(); // taskId -> workingDir
    this.completedTasks = new Set();
  }

  path_overlap(pathA, pathB) {
    const a = (pathA || '').replace(/\\/g, '/').toLowerCase().replace(/\/+$/, '');
    const b = (pathB || '').replace(/\\/g, '/').toLowerCase().replace(/\/+$/, '');
    return a === b || a.startsWith(b + '/') || b.startsWith(a + '/');
  }

  is_candidate_dispatchable(task, passport, is_fenced = false) {
    if (!task || !task.task_id) return { allowed: false, reason: 'NO_TASK_ID' };
    if (is_fenced) return { allowed: false, reason: 'FENCED' };
    if (!passport || !passport.signature) return { allowed: false, reason: 'MISSING_SIGNATURE' };

    // Verify passport signature
    const normPaths = (passport.scope_paths || []).slice().sort();
    const payload = `${passport.task_id}:${passport.task_version}:${passport.goal_id}:${normPaths.join(';')}:${passport.max_capability}:COURIER_V2`;
    const expected = crypto.createHash('sha256').update(payload).digest('hex');
    if (passport.signature !== expected) {
      return { allowed: false, reason: 'TAMPERED_PASSPORT_SIGNATURE' };
    }

    // Verify scope
    const taskPath = path.resolve(task.working_dir).toLowerCase().replace(/\\/g, '/');
    const withinScope = passport.scope_paths.some(sp => taskPath === sp || taskPath.startsWith(sp + '/'));
    if (!withinScope) {
      return { allowed: false, reason: 'OUT_OF_SCOPE_DIRECTORY' };
    }

    // Check lock conflicts against active leases
    for (const [heldTaskId, heldDir] of this.dispatchedTasks.entries()) {
      if (heldTaskId === task.task_id) continue;
      if (this.path_overlap(task.working_dir, heldDir)) {
        return { allowed: false, reason: 'RESOURCE_LOCK_CONFLICT', conflicting_task_id: heldTaskId };
      }
    }

    return { allowed: true, reason: 'DISPATCH_ALLOWED' };
  }

  result_acceptable({ exit_code, artifact_count, missing_checksums = 0, tampered_signature = false }) {
    if (exit_code !== 0) return { acceptable: false, reason: 'EXIT_NONZERO' };
    if (tampered_signature) return { acceptable: false, reason: 'TAMPERED_SIG' };
    if (artifact_count <= 0) return { acceptable: false, reason: 'NO_ARTIFACTS' };
    if (missing_checksums > 0) return { acceptable: false, reason: 'UNCHECKSUMMED_ARTIFACT' };
    return { acceptable: true, reason: 'ACCEPTED' };
  }

  goal_verified(criteriaList, evidenceList) {
    if (!criteriaList || criteriaList.length === 0) return false;
    const evSet = new Set(evidenceList);
    return criteriaList.every(c => evSet.has(c));
  }
}

module.exports = {
  ReferenceOracleV2
};
