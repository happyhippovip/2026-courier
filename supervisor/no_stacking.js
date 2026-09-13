// No-Stacking & Hierarchical Resource Collision Detector
// Invariants:
// 1. Equivalent heavy work on the SAME machine must not stack.
// 2. Overlapping NTFS resource paths (parent/child, case variants) must not be concurrently locked.
// 3. Different machines or independent resources must NOT conflict.

const crypto = require('crypto');
const path = require('path');
const { LEASE_STATUS } = require('./types');
const { ResourceLockManager } = require('../governance/ResourceLockManager');

class NoStackingDetector {
  constructor(leaseManager, lockManager = null) {
    if (!leaseManager) throw new Error('[NO_STACKING_ERROR] leaseManager is required');
    this.leaseManager = leaseManager;
    this.lockManager = lockManager || new ResourceLockManager();
  }

  static computeTaskWorkSignature(taskId, workCategory, command = '') {
    const normCmd = (command || '').trim().toLowerCase();
    const raw = `${taskId}:${workCategory}:${normCmd}`;
    return crypto.createHash('sha256').update(raw).digest('hex');
  }

  evaluateHeavyTaskSubmission({
    task_id,
    work_category = 'TEST_SUITE',
    command = '',
    machine_id = 'WINDOWS_LOCAL',
    resource_path = null,
    working_dir = null
  }) {
    // 1. Check Hierarchical Resource Lock Overlap if a path is specified
    const targetPath = resource_path || working_dir;
    if (targetPath) {
      const lockCheck = this.lockManager.canAcquire(targetPath, task_id);
      if (!lockCheck.available) {
        return {
          allowed: false,
          is_duplicate_heavy_work: true,
          status: 'RESOURCE_LOCK_CONFLICT',
          conflicting_task_id: lockCheck.conflicting_task_id,
          conflicting_path: lockCheck.conflicting_path,
          reason: `Resource conflict on '${targetPath}'. Overlaps with held lock '${lockCheck.conflicting_path}' by task '${lockCheck.conflicting_task_id}'. Stacking prevented.`
        };
      }
    }

    // 2. Command and Equivalent Work Duplicate Check on SAME Machine
    const signature = NoStackingDetector.computeTaskWorkSignature(task_id, work_category, command);
    const activeLeases = this.leaseManager.getActiveLeasesForMachine(machine_id);

    for (const lease of activeLeases) {
      if (lease.task_id === task_id) {
        const existingSig = NoStackingDetector.computeTaskWorkSignature(
          lease.task_id,
          lease.purpose || work_category,
          lease.command
        );

        if (existingSig === signature || lease.command === command) {
          return {
            allowed: false,
            is_duplicate_heavy_work: true,
            status: 'DUPLICATE_HEAVY_WORK_BLOCKED',
            canonical_lease_id: lease.process_lease_id,
            canonical_status: lease.status,
            reason: `Equivalent heavy work (${work_category}) already active on machine ${machine_id} under lease ${lease.process_lease_id}. Stacking prevented.`
          };
        }
      }
    }

    return {
      allowed: true,
      is_duplicate_heavy_work: false,
      status: 'ADMISSION_PERMITTED',
      reason: `No conflicting equivalent heavy work on machine ${machine_id}`
    };
  }

  // Direct Resource Lock API delegating to ResourceLockManager
  acquireResource(resourcePath, taskId, mode = 'EXCL') {
    return this.lockManager.acquire(resourcePath, taskId, mode);
  }

  releaseResource(resourcePath, taskId) {
    return this.lockManager.release(resourcePath, taskId);
  }

  releaseAllForTask(taskId) {
    return this.lockManager.releaseAllForTask(taskId);
  }

  canAcquireResource(resourcePath, taskId) {
    return this.lockManager.canAcquire(resourcePath, taskId);
  }

  activeResourceLocks() {
    return this.lockManager.activeLocks();
  }
}

module.exports = {
  NoStackingDetector,
  ResourceLockManager
};