/**
 * WORKER LEASE ENGINE (V2 LAB)
 * 
 * Formal worker lease capability model enforcing:
 * Strict validation of task identity, version, goal, worker, machine, and lease type.
 * Rejects stale, duplicate, cross-machine, or silently upgraded leases.
 */

const crypto = require('crypto');

class WorkerLeaseEngine {
  constructor() {
    this.leases = new Map(); // lease_id -> Lease
    this.taskToLease = new Map(); // task_id -> lease_id
    this.completedTasks = new Set();
  }

  markTaskCompleted(taskId) {
    this.completedTasks.add(taskId);
    if (this.taskToLease.has(taskId)) {
      const leaseId = this.taskToLease.get(taskId);
      this.leases.delete(leaseId);
      this.taskToLease.delete(taskId);
    }
  }

  grantLease({
    task_id,
    task_version = 1,
    goal_id,
    worker_id,
    machine_id = 'WINDOWS_LOCAL',
    lease_type = 'WRITER',
    duration_ms = 60000
  }) {
    // 1. Task already completed check
    if (this.completedTasks.has(task_id)) {
      throw new Error(`[LEASE_ERROR:ERR_TASK_ALREADY_CLOSED] Cannot grant lease for already completed task ${task_id}`);
    }

    // 2. Active lease conflict check
    if (this.taskToLease.has(task_id)) {
      const existingId = this.taskToLease.get(task_id);
      const existing = this.leases.get(existingId);
      if (existing && existing.expires_at > Date.now()) {
        if (existing.machine_id !== machine_id) {
          throw new Error(`[LEASE_ERROR:ERR_CROSS_MACHINE_CONFLICT] Task ${task_id} is locked by ${existing.machine_id}`);
        }
        throw new Error(`[LEASE_ERROR:ERR_DUPLICATE_LEASE_ACQUISITION] Task ${task_id} already has active lease ${existingId}`);
      }
    }

    const lease_id = `LEASE-${task_id}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
    const lease = {
      lease_id,
      task_id,
      task_version,
      goal_id,
      worker_id,
      machine_id,
      lease_type,
      granted_at: Date.now(),
      expires_at: Date.now() + duration_ms
    };

    this.leases.set(lease_id, lease);
    this.taskToLease.set(task_id, lease_id);
    return lease;
  }

  validateAction(lease_id, actionContext) {
    if (!lease_id || !this.leases.has(lease_id)) {
      return { allowed: false, code: 'ERR_NO_ACTIVE_LEASE', reason: 'No active lease token found' };
    }

    const lease = this.leases.get(lease_id);

    // Expiry
    if (Date.now() > lease.expires_at) {
      return { allowed: false, code: 'ERR_LEASE_EXPIRED', reason: `Lease ${lease_id} expired at ${new Date(lease.expires_at).toISOString()}` };
    }

    // Identity mismatches
    if (actionContext.worker_id && actionContext.worker_id !== lease.worker_id) {
      return { allowed: false, code: 'ERR_WRONG_WORKER', reason: `Worker mismatch: expected ${lease.worker_id}, got ${actionContext.worker_id}` };
    }
    if (actionContext.goal_id && actionContext.goal_id !== lease.goal_id) {
      return { allowed: false, code: 'ERR_WRONG_GOAL', reason: `Goal mismatch: expected ${lease.goal_id}, got ${actionContext.goal_id}` };
    }
    if (actionContext.task_id && actionContext.task_id !== lease.task_id) {
      return { allowed: false, code: 'ERR_WRONG_TASK', reason: `Task mismatch: expected ${lease.task_id}, got ${actionContext.task_id}` };
    }
    if (actionContext.task_version && actionContext.task_version !== lease.task_version) {
      return { allowed: false, code: 'ERR_WRONG_VERSION', reason: `Version mismatch: expected ${lease.task_version}, got ${actionContext.task_version}` };
    }

    // Silent Upgrade Check: Read-only lease attempting write
    if (lease.lease_type === 'READ_ONLY' && actionContext.requires_write) {
      return { allowed: false, code: 'ERR_UNAUTHORIZED_WRITE_ON_READ_LEASE', reason: 'Action requires write authority but lease is READ_ONLY' };
    }

    return { allowed: true, code: 'ALLOW', reason: 'Action authorized under active lease' };
  }
}

module.exports = { WorkerLeaseEngine };
