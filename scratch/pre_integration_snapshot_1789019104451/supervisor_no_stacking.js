// No-Stacking & Duplicate Heavy Work Detector
// Invariant: Equivalent heavy work on the SAME machine must not stack.
// Different machines or different tasks must NOT conflict.

const crypto = require('crypto');
const { LEASE_STATUS } = require('./types');

class NoStackingDetector {
  constructor(leaseManager) {
    if (!leaseManager) throw new Error('[NO_STACKING_ERROR] leaseManager is required');
    this.leaseManager = leaseManager;
  }

  static computeTaskWorkSignature(taskId, workCategory, command = '') {
    // Canonical signature representing equivalent heavy work
    const normCmd = (command || '').trim().toLowerCase();
    const raw = `${taskId}:${workCategory}:${normCmd}`;
    return crypto.createHash('sha256').update(raw).digest('hex');
  }

  evaluateHeavyTaskSubmission({
    task_id,
    work_category = 'TEST_SUITE',
    command = '',
    machine_id = 'WINDOWS_LOCAL'
  }) {
    const signature = NoStackingDetector.computeTaskWorkSignature(task_id, work_category, command);
    const activeLeases = this.leaseManager.getActiveLeasesForMachine(machine_id);

    // Look for duplicate active equivalent work on the SAME machine
    for (const lease of activeLeases) {
      if (lease.task_id === task_id) {
        const existingSig = NoStackingDetector.computeTaskWorkSignature(
          lease.task_id,
          lease.purpose || work_category,
          lease.command
        );

        if (existingSig === signature || lease.command === command) {
          // Found active canonical work
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
}

module.exports = {
  NoStackingDetector
};
