/**
 * PROCESS LEASE & MULTI-FACTOR IDENTITY ENGINE (V2 LAB)
 * 
 * Formal process lease manager enforcing:
 * NEVER identify process ownership using PID alone.
 * Multi-factor verification: (PID, PPID, StartTime, Command, TaskID, Fingerprint).
 */

const crypto = require('crypto');

class ProcessLeaseEngine {
  constructor() {
    this.activeLeases = new Map(); // lease_id -> ProcessLease
    this.taskToLease = new Map();  // task_id -> lease_id
  }

  static computeProcessFingerprint(proc) {
    const payload = {
      pid: proc.pid,
      ppid: proc.ppid,
      start_time: proc.start_time,
      command_line: proc.command_line,
      task_id: proc.task_id
    };
    return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  }

  registerProcessLease({
    task_id,
    pid,
    ppid,
    start_time,
    command_line
  }) {
    if (this.taskToLease.has(task_id)) {
      throw new Error(`[PROCESS_ERROR:ERR_TASK_PROCESS_COLLISION] Task ${task_id} already has an active process lease`);
    }

    const fingerprint = ProcessLeaseEngine.computeProcessFingerprint({
      pid,
      ppid,
      start_time,
      command_line,
      task_id
    });

    const lease_id = `P-LEASE-${task_id}-${pid}`;
    const lease = {
      lease_id,
      task_id,
      pid,
      ppid,
      start_time,
      command_line,
      fingerprint,
      registered_at: Date.now()
    };

    this.activeLeases.set(lease_id, lease);
    this.taskToLease.set(task_id, lease_id);
    return lease;
  }

  /**
   * Verifies that live OS process matches authoritative process lease.
   */
  verifyProcessOwnership(taskId, liveProcess) {
    if (!this.taskToLease.has(taskId)) {
      return { verified: false, code: 'ERR_UNTRACKED_TASK', reason: `No process lease registered for task ${taskId}` };
    }

    const leaseId = this.taskToLease.get(taskId);
    const lease = this.activeLeases.get(leaseId);

    // 1. PID match check
    if (liveProcess.pid !== lease.pid) {
      return { verified: false, code: 'ERR_PID_MISMATCH', reason: `PID mismatch: expected ${lease.pid}, got ${liveProcess.pid}` };
    }

    // 2. Start Time check (Detects PID recycling by OS)
    if (liveProcess.start_time !== lease.start_time) {
      return {
        verified: false,
        code: 'ERR_PID_RECYCLED',
        reason: `PID ${liveProcess.pid} was recycled by OS! Registered start time: ${lease.start_time}, live start time: ${liveProcess.start_time}`
      };
    }

    // 3. Command Line check (Detects PID reassignment to unrelated process)
    if (liveProcess.command_line !== lease.command_line) {
      return {
        verified: false,
        code: 'ERR_PROCESS_COMMAND_MISMATCH',
        reason: `Command line mismatch: expected '${lease.command_line}', got '${liveProcess.command_line}'`
      };
    }

    // 4. PPID check (Detects parent termination / orphan reparenting)
    if (liveProcess.ppid !== lease.ppid) {
      return {
        verified: true, // Still owned by worker, but flagged as reparented orphan
        code: 'WARN_PARENT_TERMINATED_ORPHAN',
        reason: `Parent PID changed from ${lease.ppid} to ${liveProcess.ppid} (orphan process)`
      };
    }

    return { verified: true, code: 'ALLOW', reason: 'Process ownership verified across all factors' };
  }
}

module.exports = { ProcessLeaseEngine };
