// Coherent Executable Shadow Courier Kernel — Sigma V1
// Invariant: Single-writer authority per decision; durable state over memory;
// Hierarchical capability lattice; real resource locks; atomic CAS dispatch.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// 1. CAPABILITY LATTICE (Solves CX-SIGMA-AUDIT-003)
const CAPABILITY_LEVELS = Object.freeze({
  READ_ONLY: 1,
  WORKSPACE_WRITE: 2,
  EXTERNAL_FS: 3,
  NETWORK_INSPECT: 4,
  NETWORK_CALL: 5,
  SECRETS_ACCESS: 6,
  FINANCIAL_LIABILITY: 7
});

class CapabilityLattice {
  static getLevel(capabilityName) {
    const map = {
      'READ_ONLY': 1,
      'FILE_READ': 1,
      'STATUS_CHECK': 1,
      'WORKSPACE_WRITE': 2,
      'SCRATCH_WRITE': 2,
      'LOCAL_TEST': 2,
      'EXTERNAL_FS_WRITE': 3,
      'SYSTEM_CONFIG': 3,
      'NETWORK_INSPECT': 4,
      'NETWORK_CALL': 5,
      'SECRETS_ACCESS': 6,
      'FINANCIAL_LIABILITY': 7,
      'SPEND_EUR': 7,
      'REAL_TRADE': 7,
      'WALLET_SIGN': 7
    };
    return map[capabilityName.toUpperCase()] || 99;
  }

  static authorize(requestedCap, maxAllowedLevel = CAPABILITY_LEVELS.WORKSPACE_WRITE) {
    const reqLevel = CapabilityLattice.getLevel(requestedCap);
    if (reqLevel > maxAllowedLevel) {
      return {
        allowed: false,
        required_level: reqLevel,
        max_allowed_level: maxAllowedLevel,
        requires_human_gate: reqLevel >= CAPABILITY_LEVELS.SECRETS_ACCESS,
        reason: `Requested capability '${requestedCap}' (level ${reqLevel}) exceeds maximum granted level ${maxAllowedLevel}.`
      };
    }
    return {
      allowed: true,
      required_level: reqLevel,
      max_allowed_level: maxAllowedLevel,
      requires_human_gate: false
    };
  }
}

// 2. RESOURCE LOCK MANAGER (Solves CX-SIGMA-AUDIT-002)
class ResourceLockManager {
  constructor() {
    this.locks = new Map(); // resource_key -> { task_id, acquired_at, mode: 'EXCL' | 'SHARED' }
  }

  static normalizePath(p) {
    return path.resolve(p).toLowerCase().replace(/\\/g, '/');
  }

  acquireLock(resourceKey, taskId, mode = 'EXCL') {
    const normKey = ResourceLockManager.normalizePath(resourceKey);
    // Check path overlap: parent or child directory collision
    for (const [existingKey, lock] of this.locks.entries()) {
      if (lock.task_id === taskId) continue; // Reentrant lock for same task
      const isOverlap = normKey === existingKey || 
                        normKey.startsWith(existingKey + '/') || 
                        existingKey.startsWith(normKey + '/');
      if (isOverlap) {
        return {
          acquired: false,
          conflicting_task_id: lock.task_id,
          conflicting_resource: existingKey,
          reason: `Resource lock collision: path '${normKey}' overlaps with locked resource '${existingKey}' held by task '${lock.task_id}'.`
        };
      }
    }
    this.locks.set(normKey, {
      task_id: taskId,
      acquired_at: new Date().toISOString(),
      mode
    });
    return { acquired: true, resource: normKey, task_id: taskId };
  }

  releaseLock(resourceKey, taskId) {
    const normKey = ResourceLockManager.normalizePath(resourceKey);
    const lock = this.locks.get(normKey);
    if (lock && lock.task_id === taskId) {
      this.locks.delete(normKey);
      return true;
    }
    return false;
  }

  releaseAllForTask(taskId) {
    let released = 0;
    for (const [k, lock] of this.locks.entries()) {
      if (lock.task_id === taskId) {
        this.locks.delete(k);
        released++;
      }
    }
    return released;
  }
}

// 3. FRAMED DURABLE DISK JOURNAL (Solves torn writes, crash recovery)
class FramedDurableJournal {
  constructor(journalPath) {
    this.journalPath = journalPath;
    const dir = path.dirname(journalPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    if (!fs.existsSync(this.journalPath)) fs.writeFileSync(this.journalPath, '', 'utf8');
  }

  append(entry) {
    const payload = JSON.stringify(entry);
    const checksum = crypto.createHash('sha256').update(payload).digest('hex').substring(0, 16);
    const length = Buffer.byteLength(payload, 'utf8');
    // Format: [FRAME:length:checksum]\n[PAYLOAD]\n
    const frame = `FRAME:${length}:${checksum}\n${payload}\n`;
    fs.appendFileSync(this.journalPath, frame, 'utf8');
    return checksum;
  }

  recoverAndReplay() {
    if (!fs.existsSync(this.journalPath)) return { validEntries: [], tornEntries: 0 };
    const content = fs.readFileSync(this.journalPath, 'utf8');
    const lines = content.split('\n');
    const validEntries = [];
    let tornEntries = 0;

    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      if (line.startsWith('FRAME:')) {
        const parts = line.split(':');
        const expectedLen = parseInt(parts[1], 10);
        const expectedChecksum = parts[2];
        const payloadLine = lines[i + 1];
        if (payloadLine === undefined) {
          tornEntries++;
          break; // Torn write at EOF
        }
        const actualLen = Buffer.byteLength(payloadLine, 'utf8');
        const actualChecksum = crypto.createHash('sha256').update(payloadLine).digest('hex').substring(0, 16);
        if (actualLen === expectedLen && actualChecksum === expectedChecksum) {
          try {
            validEntries.push(JSON.parse(payloadLine));
          } catch (e) {
            tornEntries++;
          }
          i += 2;
        } else {
          tornEntries++;
          i += 2;
        }
      } else {
        // Unexpected line format
        tornEntries++;
        i++;
      }
    }
    return { validEntries, tornEntries };
  }
}

// 4. ATOMIC CAS DISPATCH AUTHORITY (Solves CX-SIGMA-AUDIT-005)
class DispatchAuthority {
  constructor(journal) {
    this.journal = journal;
    this.tasks = new Map(); // task_id -> task_record
  }

  registerCandidateTask({ task_id, title, work_category, command, working_dir, version = 1 }) {
    if (this.tasks.has(task_id)) {
      throw new Error(`Task '${task_id}' already registered`);
    }
    const record = {
      task_id,
      title,
      work_category,
      command,
      working_dir,
      version,
      state: 'STAGED', // STAGED -> CLAIMED -> DISPATCHED -> COMPLETED | FAILED | EXECUTION_UNCERTAIN
      claimed_by: null,
      claimed_at: null,
      dispatched_at: null,
      completed_at: null,
      result: null
    };
    this.tasks.set(task_id, record);
    this.journal.append({ type: 'TASK_STAGED', task: record });
    return record;
  }

  // Atomic Compare-And-Swap Claim
  claimDispatchAtomic(taskId, workerId, expectedVersion = 1) {
    const task = this.tasks.get(taskId);
    if (!task) return { success: false, reason: 'TASK_NOT_FOUND' };
    if (task.version !== expectedVersion) {
      return { success: false, reason: 'VERSION_MISMATCH', current_version: task.version };
    }
    if (task.state !== 'STAGED') {
      return { success: false, reason: 'INVALID_STATE', current_state: task.state, claimed_by: task.claimed_by };
    }

    // Atomic state update
    task.state = 'CLAIMED';
    task.claimed_by = workerId;
    task.claimed_at = new Date().toISOString();
    task.version += 1;

    this.journal.append({
      type: 'TASK_CLAIMED_ATOMIC',
      task_id: taskId,
      worker_id: workerId,
      new_version: task.version,
      claimed_at: task.claimed_at
    });

    return { success: true, task };
  }

  markDispatched(taskId, workerId, leaseId) {
    const task = this.tasks.get(taskId);
    if (!task || task.claimed_by !== workerId || task.state !== 'CLAIMED') {
      return { success: false, reason: 'CANNOT_DISPATCH_UNCLAIMED_TASK' };
    }
    task.state = 'DISPATCHED';
    task.dispatched_at = new Date().toISOString();
    task.lease_id = leaseId;
    task.version += 1;

    this.journal.append({
      type: 'TASK_DISPATCHED',
      task_id: taskId,
      worker_id: workerId,
      lease_id: leaseId,
      new_version: task.version
    });
    return { success: true, task };
  }
}

// 5. PROCESS TREE MANAGER (Solves CX-SIGMA-AUDIT-004)
class ProcessTreeManager {
  constructor() {
    this.registeredProcesses = new Map(); // pid -> { pid, command, startTime, parentPid, childrenPids }
  }

  registerProcess({ pid, command, startTime = Date.now(), parentPid = null }) {
    const record = {
      pid,
      command,
      startTime,
      parentPid,
      childrenPids: new Set(),
      status: 'ACTIVE'
    };
    this.registeredProcesses.set(pid, record);
    if (parentPid && this.registeredProcesses.has(parentPid)) {
      this.registeredProcesses.get(parentPid).childrenPids.add(pid);
    }
    return record;
  }

  verifyIdentity(pid, expectedStartTime, expectedCommand) {
    const proc = this.registeredProcesses.get(pid);
    if (!proc) return { match: false, reason: 'PID_NOT_REGISTERED' };
    if (Math.abs(proc.startTime - expectedStartTime) > 2000) {
      return { match: false, reason: 'START_TIME_MISMATCH_PID_RECYCLED' };
    }
    if (expectedCommand && proc.command !== expectedCommand) {
      return { match: false, reason: 'COMMAND_MISMATCH' };
    }
    return { match: true, proc };
  }

  collectDescendants(pid) {
    const descendants = [];
    const queue = [pid];
    while (queue.length > 0) {
      const curr = queue.shift();
      const p = this.registeredProcesses.get(curr);
      if (p && p.childrenPids) {
        for (const childPid of p.childrenPids) {
          descendants.push(childPid);
          queue.push(childPid);
        }
      }
    }
    return descendants;
  }
}

// 6. UNIFIED SHADOW COURIER KERNEL
class ShadowCourierKernel {
  constructor(storageDir) {
    this.storageDir = storageDir || path.join(__dirname, 'data');
    if (!fs.existsSync(this.storageDir)) fs.mkdirSync(this.storageDir, { recursive: true });

    this.journal = new FramedDurableJournal(path.join(this.storageDir, 'durable_journal.log'));
    this.lockManager = new ResourceLockManager();
    this.dispatchAuthority = new DispatchAuthority(this.journal);
    this.processTreeManager = new ProcessTreeManager();
    this.goals = new Map();
    this.followUps = [];
    this.uncertaintyFences = new Set();
  }

  createGoal(goalId, title, successCriteria) {
    const goal = {
      goal_id: goalId,
      title,
      success_criteria: successCriteria,
      status: 'ACTIVE',
      created_at: new Date().toISOString(),
      satisfied_at: null,
      evidence: []
    };
    this.goals.set(goalId, goal);
    this.journal.append({ type: 'GOAL_CREATED', goal });
    return goal;
  }

  stageAndAcquireTask({ taskId, title, workCategory, command, workingDir, requiredCap = 'WORKSPACE_WRITE' }) {
    // 1. Check capability lattice
    const capCheck = CapabilityLattice.authorize(requiredCap);
    if (!capCheck.allowed) {
      return { admitted: false, failure_stage: 'CAPABILITY_LATTICE', reason: capCheck.reason };
    }

    // 2. Check resource lock
    const lockCheck = this.lockManager.acquireLock(workingDir, taskId);
    if (!lockCheck.acquired) {
      return { admitted: false, failure_stage: 'RESOURCE_LOCK', reason: lockCheck.reason };
    }

    // 3. Register in DispatchAuthority
    const task = this.dispatchAuthority.registerCandidateTask({
      task_id: taskId,
      title,
      work_category: workCategory,
      command,
      working_dir: workingDir
    });

    return { admitted: true, task, resource_locked: lockCheck.resource };
  }

  dispatchWorkerAtomic(taskId, workerId) {
    if (this.uncertaintyFences.has(taskId)) {
      return { dispatched: false, reason: 'EXECUTION_UNCERTAIN_FENCE_ACTIVE' };
    }

    const claimRes = this.dispatchAuthority.claimDispatchAtomic(taskId, workerId, 1);
    if (!claimRes.success) {
      return { dispatched: false, reason: claimRes.reason };
    }

    const leaseId = `SHADOW-LEASE-${Date.now()}-${Math.floor(Math.random()*10000)}`;
    const dispRes = this.dispatchAuthority.markDispatched(taskId, workerId, leaseId);
    return { dispatched: true, lease_id: leaseId, task: dispRes.task };
  }

  markExecutionUncertain(taskId, reason) {
    this.uncertaintyFences.add(taskId);
    this.journal.append({
      type: 'EXECUTION_UNCERTAIN_FENCE',
      task_id: taskId,
      reason,
      timestamp: new Date().toISOString()
    });
  }

  captureFollowUp(followUp) {
    const entry = {
      id: `FOLLOW-${Date.now()}-${this.followUps.length + 1}`,
      ...followUp,
      created_at: new Date().toISOString()
    };
    this.followUps.push(entry);
    this.journal.append({ type: 'FOLLOW_UP_CAPTURED', followUp: entry });
    return entry;
  }
}

module.exports = {
  ShadowCourierKernel,
  CapabilityLattice,
  ResourceLockManager,
  FramedDurableJournal,
  DispatchAuthority,
  ProcessTreeManager,
  CAPABILITY_LEVELS
};
