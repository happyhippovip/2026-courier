// Worker & Process Lease Managers
class WorkerLeaseManager {
  constructor() {
    this.leases = new Map(); // workerId -> lease
  }

  acquire(workerId, taskId, taskVersion = 1, leaseType = 'EXCLUSIVE_EXECUTION') {
    const lease = {
      worker_id: workerId,
      active_task_id: taskId,
      task_version: taskVersion,
      lease_type: leaseType,
      acquired_at: new Date().toISOString(),
      heartbeat: Date.now(),
      state: 'ACTIVE'
    };
    this.leases.set(workerId, lease);
    return lease;
  }

  heartbeat(workerId) {
    const lease = this.leases.get(workerId);
    if (lease) lease.heartbeat = Date.now();
  }

  release(workerId) {
    return this.leases.delete(workerId);
  }

  getLease(workerId) {
    return this.leases.get(workerId);
  }
}

class ProcessLeaseManager {
  constructor() {
    this.processes = new Map(); // pid -> rec
  }

  register({ pid, startTime = Date.now(), taskToken, taskId, purpose = 'WORKER_SUBPROCESS' }) {
    const rec = {
      process_lease_id: `P-LEASE-${pid}-${startTime}`,
      pid,
      start_time: startTime,
      task_token: taskToken,
      task_id: taskId,
      purpose,
      registered_at: new Date().toISOString(),
      heartbeat: Date.now(),
      status: 'ACTIVE'
    };
    this.processes.set(pid, rec);
    return rec;
  }

  verifyIdentity(pid, expectedStartTime, expectedTaskToken) {
    const rec = this.processes.get(pid);
    if (!rec) return { valid: false, reason: 'PROCESS_NOT_REGISTERED' };
    if (Math.abs(rec.start_time - expectedStartTime) > 1500) {
      return { valid: false, reason: 'RECYCLED_PID_START_TIME_MISMATCH' };
    }
    if (expectedTaskToken && rec.task_token !== expectedTaskToken) {
      return { valid: false, reason: 'TASK_TOKEN_MISMATCH' };
    }
    return { valid: true, processRecord: rec };
  }

  deregister(pid) {
    return this.processes.delete(pid);
  }
}

module.exports = {
  WorkerLeaseManager,
  ProcessLeaseManager
};
