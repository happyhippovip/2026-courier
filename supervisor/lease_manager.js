// Process Lease Manager — Durable Process Ownership & Parent-Child Reconciliation
// Invariants:
// 1. Process identity = PID + START_TIME + TASK_TOKEN.
// 2. UNKNOWN process identity must NEVER authorize destructive cleanup.
// 3. Historical lease records must not be silently deleted.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { LEASE_STATUS, EVENT_TYPE } = require('./types');

class ProcessLeaseManager {
  constructor(storageDir = null, auditLedger = null) {
    this.storageDir = storageDir || path.join(__dirname, '..', 'runtime', 'leases');
    if (!fs.existsSync(this.storageDir)) {
      fs.mkdirSync(this.storageDir, { recursive: true });
    }
    this.leasesFile = path.join(this.storageDir, 'leases.json');
    this.auditLedger = auditLedger;

    this.leases = new Map();
    this._load();
  }

  _load() {
    if (fs.existsSync(this.leasesFile)) {
      try {
        const raw = JSON.parse(fs.readFileSync(this.leasesFile, 'utf8'));
        if (Array.isArray(raw)) {
          for (const l of raw) {
            this.leases.set(l.process_lease_id, l);
          }
        }
      } catch (err) {
        console.error(`[LEASE_MANAGER] Warning: could not parse ${this.leasesFile}:`, err.message);
      }
    }
  }

  _persist() {
    const list = Array.from(this.leases.values());
    const tmp = `${this.leasesFile}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(list, null, 2), 'utf8');
    fs.renameSync(tmp, this.leasesFile);
  }

  static computeProcessFingerprint(command, pid, machineId, startedAt, taskToken = '') {
    const raw = `${machineId}:${pid}:${startedAt}:${command}:${taskToken}`;
    return crypto.createHash('sha256').update(raw).digest('hex');
  }

  static computeCommandFingerprint(command) {
    return crypto.createHash('sha256').update(command || '').digest('hex');
  }

  createLease({
    task_id,
    task_version = 1,
    goal_id = null,
    worker_id = null,
    owner = 'COURIER_WORKER',
    machine_id = 'WINDOWS_LOCAL',
    pid = process.pid,
    command = '',
    purpose = 'GENERAL_WORK',
    expected_completion_condition = 'EXIT_ZERO',
    cleanup_policy = 'TERMINATE_ON_TASK_END',
    parent_process_id = null,
    status = LEASE_STATUS.STARTING,
    task_token = null,
    start_time_epoch = null
  }) {
    if (!task_id) throw new Error('[LEASE_ERROR] task_id is required');

    const startedAt = new Date().toISOString();
    const startTimeEpoch = start_time_epoch || Date.now();
    const token = task_token || `TOKEN-${task_id}-${crypto.randomBytes(6).toString('hex').toUpperCase()}`;
    const leaseId = `LEASE-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
    const pFp = ProcessLeaseManager.computeProcessFingerprint(command, pid, machine_id, startedAt, token);
    const cFp = ProcessLeaseManager.computeCommandFingerprint(command);

    const lease = {
      process_lease_id: leaseId,
      task_id,
      task_version,
      goal_id,
      worker_id,
      owner,
      machine_id,
      pid,
      command,
      process_fingerprint: pFp,
      command_fingerprint: cFp,
      task_token: token,
      start_time_epoch: startTimeEpoch,
      purpose,
      started_at: startedAt,
      last_heartbeat_at: startedAt,
      last_progress_at: startedAt,
      expected_completion_condition,
      cleanup_policy,
      parent_process_id,
      status,
      termination_reason: null,
      result_reference: null,
      history: [
        {
          timestamp: startedAt,
          status,
          note: 'Lease created'
        }
      ]
    };

    this.leases.set(leaseId, lease);
    this._persist();

    if (this.auditLedger) {
      this.auditLedger.recordEvent({
        task_id,
        task_version,
        goal_id,
        worker_id,
        process_lease_id: leaseId,
        machine_id,
        event_type: EVENT_TYPE.PROCESS_REGISTERED,
        new_state: status,
        reason_codes: ['LEASE_ACQUIRED']
      });
    }

    return lease;
  }

  getLease(leaseId) {
    return this.leases.get(leaseId) || null;
  }

  getLeaseByPid(pid) {
    for (const l of this.leases.values()) {
      if (l.pid === pid) return l;
    }
    return null;
  }

  getAllLeases() {
    return Array.from(this.leases.values());
  }

  getActiveLeasesForMachine(machineId) {
    const activeStatuses = [
      LEASE_STATUS.STARTING,
      LEASE_STATUS.RUNNING,
      LEASE_STATUS.WAITING_VALID,
      LEASE_STATUS.PROGRESSING,
      LEASE_STATUS.STALLED,
      LEASE_STATUS.EXECUTION_UNCERTAIN
    ];
    return this.getAllLeases().filter(l => l.machine_id === machineId && activeStatuses.includes(l.status));
  }

  recordHeartbeat(leaseId, timestamp = null) {
    const lease = this.leases.get(leaseId);
    if (!lease) throw new Error(`[LEASE_ERROR] Lease '${leaseId}' not found`);

    const ts = timestamp || new Date().toISOString();
    lease.last_heartbeat_at = ts;
    this._persist();

    if (this.auditLedger) {
      this.auditLedger.recordEvent({
        task_id: lease.task_id,
        task_version: lease.task_version,
        goal_id: lease.goal_id,
        worker_id: lease.worker_id,
        process_lease_id: leaseId,
        machine_id: lease.machine_id,
        event_type: EVENT_TYPE.HEARTBEAT,
        new_state: lease.status,
        reason_codes: ['HEARTBEAT_RECORDED']
      });
    }

    return lease;
  }

  updateStatus(leaseId, newStatus, reason = null, resultRef = null) {
    const lease = this.leases.get(leaseId);
    if (!lease) throw new Error(`[LEASE_ERROR] Lease '${leaseId}' not found`);

    const prevStatus = lease.status;
    lease.status = newStatus;
    if (reason) lease.termination_reason = reason;
    if (resultRef) lease.result_reference = resultRef;

    const now = new Date().toISOString();
    lease.history.push({
      timestamp: now,
      status: newStatus,
      note: reason || 'Status transition'
    });

    this._persist();

    if (this.auditLedger) {
      this.auditLedger.recordEvent({
        task_id: lease.task_id,
        task_version: lease.task_version,
        goal_id: lease.goal_id,
        worker_id: lease.worker_id,
        process_lease_id: leaseId,
        machine_id: lease.machine_id,
        event_type: EVENT_TYPE.STATE_CLASSIFIED,
        previous_state: prevStatus,
        new_state: newStatus,
        reason_codes: reason ? [reason] : []
      });
    }

    return lease;
  }

  // Authoritative Process Identity Verification (GAP-002 / B01)
  verifyProcessIdentity(pid, expectedStartTimeEpoch = null, expectedTaskToken = null) {
    const lease = this.getLeaseByPid(pid);
    if (!lease) {
      return {
        valid: false,
        can_terminate: false,
        reason: 'UNKNOWN_PROCESS_IDENTITY_NEVER_AUTHORIZES_KILL',
        status: 'UNVERIFIED'
      };
    }

    // Check Start Time Tolerance to catch recycled PIDs
    if (expectedStartTimeEpoch !== null && lease.start_time_epoch) {
      const deltaMs = Math.abs(lease.start_time_epoch - expectedStartTimeEpoch);
      if (deltaMs > 2000) {
        return {
          valid: false,
          can_terminate: false,
          reason: `RECYCLED_PID_START_TIME_MISMATCH (delta ${deltaMs}ms > 2000ms)`,
          status: 'PID_REUSED'
        };
      }
    }

    // Check Task Token
    if (expectedTaskToken !== null && lease.task_token !== expectedTaskToken) {
      return {
        valid: false,
        can_terminate: false,
        reason: 'STALE_OR_FORGED_TASK_TOKEN_MISMATCH',
        status: 'TOKEN_MISMATCH'
      };
    }

    return {
      valid: true,
      can_terminate: true,
      lease,
      status: 'VERIFIED_OWNED_PROCESS'
    };
  }

  // Safe Termination: UNKNOWN or unverified process identity must NEVER authorize kill
  safeTerminateProcess(leaseId, expectedToken = null) {
    const lease = this.getLease(leaseId);
    if (!lease) {
      return {
        terminated: false,
        reason: 'UNKNOWN_LEASE_DENIED_KILL',
        can_terminate: false
      };
    }

    if (expectedToken && lease.task_token !== expectedToken) {
      return {
        terminated: false,
        reason: 'TASK_TOKEN_MISMATCH_DENIED_KILL',
        can_terminate: false
      };
    }

    this.updateStatus(leaseId, LEASE_STATUS.TERMINATED, 'SAFE_VERIFIED_TERMINATION');
    return {
      terminated: true,
      leaseId,
      status: LEASE_STATUS.TERMINATED
    };
  }

  reconcileChildrenOnParentCompletion(parentLeaseId, completionReason = 'PARENT_COMPLETED') {
    const parent = this.leases.get(parentLeaseId);
    if (!parent) return [];

    const children = this.getAllLeases().filter(l => l.parent_process_id === parentLeaseId);
    const reconciled = [];

    for (const child of children) {
      if (child.cleanup_policy === 'TERMINATE_ON_TASK_END' && child.status !== LEASE_STATUS.COMPLETED && child.status !== LEASE_STATUS.TERMINATED) {
        this.updateStatus(child.process_lease_id, LEASE_STATUS.TERMINATED, `Parent ${parentLeaseId} completed: ${completionReason}`);
        reconciled.push({ child_id: child.process_lease_id, action: 'TERMINATED', reason: completionReason });
      } else if (child.cleanup_policy === 'PRESERVE_BACKGROUND') {
        this.updateStatus(child.process_lease_id, LEASE_STATUS.WAITING_VALID, `Retained background task after parent ${parentLeaseId} completed`);
        reconciled.push({ child_id: child.process_lease_id, action: 'PRESERVED', reason: 'PRESERVE_BACKGROUND policy' });
      }
    }

    return reconciled;
  }

  reconcileDeadProcesses(machineId = 'WINDOWS_LOCAL') {
    const active = this.getActiveLeasesForMachine(machineId);
    const reconciled = [];
    for (const lease of active) {
      if (lease.pid) {
        try {
          process.kill(lease.pid, 0);
        } catch (err) {
          if (err.code === 'ESRCH') {
            this.updateStatus(lease.process_lease_id, LEASE_STATUS.COMPLETED, 'PROCESS_EXITED_CONFIRMED');
            reconciled.push({ leaseId: lease.process_lease_id, pid: lease.pid, action: 'RECONCILED_COMPLETED' });
          }
        }
      }
    }
    return reconciled;
  }
}

module.exports = {
  ProcessLeaseManager
};