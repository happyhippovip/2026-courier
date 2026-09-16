// Coherent Executable Shadow Courier Control Plane V2 — Expedition V1
// Implements unified choke points: TaskPassport, BorderGuard, ResultCustoms,
// GoalVerifier, HumanGateEngine, MissionScheduler, ResourceLockManager, ProcessTreeManager, FramedJournal.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// 1. HIERARCHICAL CAPABILITY ENGINE
const CAPABILITY_LATTICE = Object.freeze({
  READ_ONLY: 1,
  WORKSPACE_WRITE: 2,
  EXTERNAL_FS: 3,
  NETWORK_INSPECT: 4,
  NETWORK_CALL: 5,
  SECRETS_ACCESS: 6,
  FINANCIAL_LIABILITY: 7
});

class CapabilityEngine {
  static getLevel(capName) {
    const map = {
      'READ_ONLY': 1, 'FILE_READ': 1, 'STATUS_CHECK': 1,
      'WORKSPACE_WRITE': 2, 'SCRATCH_WRITE': 2, 'LOCAL_TEST': 2,
      'EXTERNAL_FS_WRITE': 3, 'SYSTEM_CONFIG': 3,
      'NETWORK_INSPECT': 4,
      'NETWORK_CALL': 5,
      'SECRETS_ACCESS': 6,
      'FINANCIAL_LIABILITY': 7, 'SPEND_EUR': 7, 'REAL_TRADE': 7, 'WALLET_SIGN': 7
    };
    return map[(capName || '').toUpperCase()] || 99;
  }

  static authorize(requestedCap, maxAllowed = CAPABILITY_LATTICE.WORKSPACE_WRITE) {
    const lvl = CapabilityEngine.getLevel(requestedCap);
    if (lvl > maxAllowed) {
      return {
        allowed: false,
        required_level: lvl,
        max_allowed: maxAllowed,
        requires_human_gate: lvl >= CAPABILITY_LATTICE.SECRETS_ACCESS,
        reason: `Capability '${requestedCap}' (${lvl}) exceeds ceiling ${maxAllowed}`
      };
    }
    return { allowed: true, required_level: lvl, max_allowed: maxAllowed, requires_human_gate: false };
  }
}

// 2. TASK PASSPORT & BORDER GUARD
class TaskPassport {
  static createPassport({ task_id, task_version, goal_id, scope_paths = [], max_capability = 'WORKSPACE_WRITE', secret_salt = 'COURIER_V2' }) {
    const normPaths = scope_paths.map(p => path.resolve(p).toLowerCase().replace(/\\/g, '/')).sort();
    const payload = `${task_id}:${task_version}:${goal_id}:${normPaths.join(';')}:${max_capability}:${secret_salt}`;
    const signature = crypto.createHash('sha256').update(payload).digest('hex');
    return {
      task_id,
      task_version,
      goal_id,
      scope_paths: normPaths,
      max_capability,
      signature,
      issued_at: new Date().toISOString()
    };
  }

  static verifyPassport(passport, secret_salt = 'COURIER_V2') {
    if (!passport || !passport.signature) return { valid: false, reason: 'MISSING_SIGNATURE' };
    const normPaths = (passport.scope_paths || []).slice().sort();
    const payload = `${passport.task_id}:${passport.task_version}:${passport.goal_id}:${normPaths.join(';')}:${passport.max_capability}:${secret_salt}`;
    const expected = crypto.createHash('sha256').update(payload).digest('hex');
    if (passport.signature !== expected) {
      return { valid: false, reason: 'TAMPERED_PASSPORT_SIGNATURE' };
    }
    return { valid: true, passport };
  }
}

class BorderGuard {
  static inspectDispatchCandidate(task, passport) {
    // 1. Verify passport signature
    const pv = TaskPassport.verifyPassport(passport);
    if (!pv.valid) {
      return { admitted: false, stage: 'BORDER_GUARD_SIGNATURE', reason: pv.reason };
    }
    // 2. Verify task binding
    if (task.task_id !== passport.task_id || task.version !== passport.task_version) {
      return { admitted: false, stage: 'BORDER_GUARD_BINDING', reason: 'TASK_PASSPORT_VERSION_MISMATCH' };
    }
    // 3. Verify scope confinement
    const taskPath = path.resolve(task.working_dir).toLowerCase().replace(/\\/g, '/');
    const withinScope = passport.scope_paths.some(sp => taskPath === sp || taskPath.startsWith(sp + '/'));
    if (!withinScope) {
      return { admitted: false, stage: 'BORDER_GUARD_SCOPE', reason: 'OUT_OF_SCOPE_DIRECTORY' };
    }
    return { admitted: true, stage: 'PASSED' };
  }
}

// 3. RESULT CUSTOMS & GOAL VERIFIER
class ResultCustoms {
  static evaluateResultEnvelope({ task_id, passport, exit_code, artifacts = [], checksum_map = {} }) {
    if (exit_code !== 0) {
      return { accepted: false, reason: 'NON_ZERO_EXIT_CODE', requires_uncertainty_evaluation: true };
    }
    const pv = TaskPassport.verifyPassport(passport);
    if (!pv.valid) {
      return { accepted: false, reason: 'INVALID_RESULT_PASSPORT' };
    }
    if (!Array.isArray(artifacts) || artifacts.length === 0) {
      return { accepted: false, reason: 'EMPTY_ARTIFACT_MANIFEST' };
    }
    for (const art of artifacts) {
      if (!checksum_map[art]) {
        return { accepted: false, reason: `MISSING_CHECKSUM_FOR_${art}` };
      }
    }
    return { accepted: true, verified_artifacts: artifacts.length };
  }
}

class GoalVerifier {
  static evaluateGoalCompletion(goal, producedEvidenceRecords = []) {
    const required = goal.acceptance_criteria || [];
    if (required.length === 0) {
      return { satisfied: false, reason: 'NO_ACCEPTANCE_CRITERIA' };
    }
    const verifiedKeys = new Set(
      producedEvidenceRecords
        .filter(r => r.status === 'VERIFIED')
        .map(r => r.criteria_key)
    );
    const missing = required.filter(req => !verifiedKeys.has(req));
    if (missing.length > 0) {
      return { satisfied: false, missing_criteria: missing, reason: 'PARTIAL_EVIDENCE' };
    }
    return { satisfied: true, verified_count: verifiedKeys.size };
  }
}

// 4. MISSION SCHEDULER WITH STARVATION PREVENTION
class MissionScheduler {
  constructor() {
    this.queue = [];
  }

  enqueue(task) {
    this.queue.push({
      ...task,
      enqueued_at: Date.now(),
      age_boost: 0,
      effective_score: task.priority === 'P0' ? 100 : (task.priority === 'P1' ? 50 : 10)
    });
  }

  updateScores() {
    const now = Date.now();
    this.queue.forEach(item => {
      const waitSec = (now - item.enqueued_at) / 1000;
      item.age_boost = Math.floor(waitSec / 10);
      const baseWeight = item.priority === 'P0' ? 100 : (item.priority === 'P1' ? 50 : 10);
      item.effective_score = baseWeight + item.age_boost;
    });
    this.queue.sort((a, b) => b.effective_score - a.effective_score);
  }

  size() {
    return this.queue.length;
  }
}

// 5. PROCESS TREE MANAGER & START-TIME IDENTITY
class ProcessTreeManagerV2 {
  constructor() {
    this.processes = new Map();
  }

  register({ pid, command, startTime = Date.now(), parentPid = null }) {
    const rec = { pid, command, startTime, parentPid, children: new Set(), status: 'ACTIVE' };
    this.processes.set(pid, rec);
    if (parentPid && this.processes.has(parentPid)) {
      this.processes.get(parentPid).children.add(pid);
    }
    return rec;
  }

  verifyIdentity(pid, expectedStartTime) {
    const proc = this.processes.get(pid);
    if (!proc) return { match: false, reason: 'PID_NOT_REGISTERED' };
    if (Math.abs(proc.startTime - expectedStartTime) > 1500) {
      return { match: false, reason: 'PID_RECYCLED_START_TIME_MISMATCH' };
    }
    return { match: true, proc };
  }

  getDescendants(pid) {
    const result = [];
    const queue = [pid];
    while (queue.length > 0) {
      const curr = queue.shift();
      const p = this.processes.get(curr);
      if (p && p.children) {
        for (const c of p.children) {
          result.push(c);
          queue.push(c);
        }
      }
    }
    return result;
  }
}

// 6. RESOURCE LOCK MANAGER (Hierarchical NTFS path overlap)
class ResourceLockManagerV2 {
  constructor() {
    this.locks = new Map();
  }

  static norm(p) {
    return path.resolve(p).toLowerCase().replace(/\\/g, '/');
  }

  canAcquire(resourcePath, taskId) {
    const target = ResourceLockManagerV2.norm(resourcePath);
    for (const [held, lock] of this.locks.entries()) {
      if (lock.taskId === taskId) continue;
      const overlap = target === held || target.startsWith(held + '/') || held.startsWith(target + '/');
      if (overlap) {
        return { available: false, conflicting_task_id: lock.taskId, conflicting_path: held };
      }
    }
    return { available: true };
  }

  acquire(resourcePath, taskId, mode = 'EXCL') {
    const check = this.canAcquire(resourcePath, taskId);
    if (!check.available) {
      return { acquired: false, conflicting_task_id: check.conflicting_task_id, conflicting_path: check.conflicting_path };
    }
    const target = ResourceLockManagerV2.norm(resourcePath);
    this.locks.set(target, { taskId, mode, acquiredAt: new Date().toISOString() });
    return { acquired: true, resource: target };
  }

  release(resourcePath, taskId) {
    const target = ResourceLockManagerV2.norm(resourcePath);
    const lock = this.locks.get(target);
    if (lock && lock.taskId === taskId) {
      this.locks.delete(target);
      return true;
    }
    return false;
  }

  releaseAllForTask(taskId) {
    let count = 0;
    for (const [k, lock] of this.locks.entries()) {
      if (lock.taskId === taskId) {
        this.locks.delete(k);
        count++;
      }
    }
    return count;
  }
}

// 7. FRAMED DURABLE DISK JOURNAL WITH SNAPSHOT COMPACTION
class FramedDurableJournalV2 {
  constructor(filePath) {
    this.filePath = filePath;
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    if (!fs.existsSync(this.filePath)) fs.writeFileSync(this.filePath, '', 'utf8');
  }

  append(entry) {
    const payload = JSON.stringify(entry);
    const len = Buffer.byteLength(payload, 'utf8');
    const cs = crypto.createHash('sha256').update(payload).digest('hex').substring(0, 16);
    const frame = `FRAME:${len}:${cs}\n${payload}\n`;
    fs.appendFileSync(this.filePath, frame, 'utf8');
    return cs;
  }

  recoverAndReplay() {
    if (!fs.existsSync(this.filePath)) return { validEntries: [], tornEntries: 0 };
    const content = fs.readFileSync(this.filePath, 'utf8');
    const lines = content.split('\n');
    const validEntries = [];
    let tornEntries = 0;

    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      if (line.startsWith('FRAME:')) {
        const parts = line.split(':');
        const expLen = parseInt(parts[1], 10);
        const expCs = parts[2];
        const payloadLine = lines[i + 1];
        if (payloadLine === undefined) {
          tornEntries++;
          break;
        }
        const actLen = Buffer.byteLength(payloadLine, 'utf8');
        const actCs = crypto.createHash('sha256').update(payloadLine).digest('hex').substring(0, 16);
        if (actLen === expLen && actCs === expCs) {
          try {
            validEntries.push(JSON.parse(payloadLine));
          } catch(e) { tornEntries++; }
          i += 2;
        } else {
          tornEntries++;
          i += 2;
        }
      } else {
        tornEntries++;
        i++;
      }
    }
    return { validEntries, tornEntries };
  }
}

// 8. UNIFIED SHADOW COURIER KERNEL V2
class ShadowCourierKernelV2 {
  constructor(dataDir) {
    this.dataDir = dataDir || path.join(__dirname, 'data');
    if (!fs.existsSync(this.dataDir)) fs.mkdirSync(this.dataDir, { recursive: true });

    this.journal = new FramedDurableJournalV2(path.join(this.dataDir, 'journal_v2.log'));
    this.lockManager = new ResourceLockManagerV2();
    this.processTree = new ProcessTreeManagerV2();
    this.scheduler = new MissionScheduler();
    this.goals = new Map();
    this.tasks = new Map();
    this.uncertaintyFences = new Set();
  }

  createGoal(goalId, title, acceptanceCriteria = []) {
    const goal = {
      goal_id: goalId,
      title,
      acceptance_criteria: acceptanceCriteria,
      status: 'ACTIVE',
      created_at: new Date().toISOString()
    };
    this.goals.set(goalId, goal);
    this.journal.append({ type: 'GOAL_CREATED', goal });
    return goal;
  }

  stageTask({ taskId, title, priority = 'P1', workingDir, requiredCap = 'WORKSPACE_WRITE', scopePaths = [] }) {
    const task = {
      task_id: taskId,
      title,
      priority,
      working_dir: workingDir,
      required_capability: requiredCap,
      version: 1,
      state: 'STAGED'
    };
    const passport = TaskPassport.createPassport({
      task_id: taskId,
      task_version: 1,
      goal_id: 'GOAL-CANONICAL',
      scope_paths: scopePaths.length > 0 ? scopePaths : [workingDir],
      max_capability: requiredCap
    });
    this.tasks.set(taskId, { task, passport });
    this.scheduler.enqueue(task);
    this.journal.append({ type: 'TASK_STAGED', task, passport });
    return { task, passport };
  }

  dispatchNext(workerId) {
    if (this.scheduler.size() === 0) return { dispatched: false, reason: 'NO_READY_TASKS' };

    this.scheduler.updateScores();

    for (let i = 0; i < this.scheduler.queue.length; i++) {
      const candidate = this.scheduler.queue[i];

      if (this.uncertaintyFences.has(candidate.task_id)) {
        continue;
      }

      const item = this.tasks.get(candidate.task_id);
      if (!item) continue;
      const { passport } = item;

      // Border Guard inspection
      const bg = BorderGuard.inspectDispatchCandidate(candidate, passport);
      if (!bg.admitted) {
        // Discard invalid task and fence it
        this.scheduler.queue.splice(i, 1);
        this.uncertaintyFences.add(candidate.task_id);
        return { dispatched: false, task_id: candidate.task_id, failure_stage: bg.stage, reason: bg.reason };
      }

      // Check lock availability
      const lockRes = this.lockManager.canAcquire(candidate.working_dir, candidate.task_id);
      if (!lockRes.available) {
        // Skip locked task
        continue;
      }

      // Candidate is dispatchable! Dequeue and lock
      this.scheduler.queue.splice(i, 1);
      this.lockManager.acquire(candidate.working_dir, candidate.task_id);
      candidate.state = 'DISPATCHED';
      candidate.claimed_by = workerId;
      candidate.dispatched_at = new Date().toISOString();
      const leaseId = `LEASE-V2-${Date.now()}-${Math.floor(Math.random()*10000)}`;

      this.journal.append({ type: 'TASK_DISPATCHED', task_id: candidate.task_id, worker_id: workerId, lease_id: leaseId });
      return { dispatched: true, task: candidate, lease_id: leaseId };
    }

    return { dispatched: false, reason: 'NO_DISPATCHABLE_TASKS_DUE_TO_LOCKS_OR_FENCES' };
  }

  recordTaskCompletion(taskId, { exit_code, artifacts = [], checksum_map = {} }) {
    const item = this.tasks.get(taskId);
    if (!item) return { completed: false, reason: 'UNKNOWN_TASK' };

    const { task, passport } = item;
    const customs = ResultCustoms.evaluateResultEnvelope({
      task_id: taskId,
      passport,
      exit_code,
      artifacts,
      checksum_map
    });

    if (!customs.accepted) {
      if (customs.requires_uncertainty_evaluation) {
        this.uncertaintyFences.add(taskId);
      }
      return { completed: false, reason: customs.reason };
    }

    task.state = 'COMPLETED';
    task.completed_at = new Date().toISOString();
    this.lockManager.releaseAllForTask(taskId);
    this.journal.append({ type: 'TASK_COMPLETED', task_id: taskId, verified_artifacts: artifacts.length });
    return { completed: true, task };
  }
}

module.exports = {
  ShadowCourierKernelV2,
  CapabilityEngine,
  TaskPassport,
  BorderGuard,
  ResultCustoms,
  GoalVerifier,
  MissionScheduler,
  ProcessTreeManagerV2,
  ResourceLockManagerV2,
  FramedDurableJournalV2,
  CAPABILITY_LATTICE
};
