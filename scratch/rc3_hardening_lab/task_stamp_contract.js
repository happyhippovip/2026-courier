/**
 * TASK STAMP / NO-STACKING CONTRACT MODEL (ISOLATED LAB)
 * 
 * Formal state machine and writer-lease contract for Courier tasks.
 * Enforces:
 * 1. Monotonic lifecycle progression:
 *    PROPOSED -> NEGOTIATING -> APPROVED_FOR_DISPATCH -> STAMPED -> DISPATCHED -> IN_FLIGHT -> RESULT_RECEIVED -> VERIFIED -> CLOSED
 * 2. Alternative states:
 *    QUESTION, CONFLICT, BLOCKED, HUMAN_GATE, CANCEL_REQUESTED, CANCELLED, FAILED
 * 3. Exactly one active writer lease per conflicting scope; second writer placed on HOLD.
 * 4. Task definition is strictly immutable once STAMPED/DISPATCHED.
 * 5. In-flight tasks cannot be mutated by incoming ideas (follow-up preserved out-of-band).
 * 6. New version supersedes old version explicitly.
 * 7. EXECUTION_UNCERTAIN blocks replacement dispatch without human resolution.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const TASK_STATE = Object.freeze({
  PROPOSED: 'PROPOSED',
  NEGOTIATING: 'NEGOTIATING',
  APPROVED_FOR_DISPATCH: 'APPROVED_FOR_DISPATCH',
  STAMPED: 'STAMPED',
  DISPATCHED: 'DISPATCHED',
  IN_FLIGHT: 'IN_FLIGHT',
  RESULT_RECEIVED: 'RESULT_RECEIVED',
  VERIFIED: 'VERIFIED',
  CLOSED: 'CLOSED',

  // Alternatives / Divergent
  QUESTION: 'QUESTION',
  CONFLICT: 'CONFLICT',
  BLOCKED: 'BLOCKED',
  HUMAN_GATE: 'HUMAN_GATE',
  CANCEL_REQUESTED: 'CANCEL_REQUESTED',
  CANCELLED: 'CANCELLED',
  FAILED: 'FAILED'
});

const VALID_TRANSITIONS = {
  [TASK_STATE.PROPOSED]: [TASK_STATE.NEGOTIATING, TASK_STATE.QUESTION, TASK_STATE.CONFLICT, TASK_STATE.BLOCKED, TASK_STATE.CANCELLED],
  [TASK_STATE.NEGOTIATING]: [TASK_STATE.APPROVED_FOR_DISPATCH, TASK_STATE.QUESTION, TASK_STATE.CONFLICT, TASK_STATE.BLOCKED, TASK_STATE.CANCELLED],
  [TASK_STATE.APPROVED_FOR_DISPATCH]: [TASK_STATE.STAMPED, TASK_STATE.HUMAN_GATE, TASK_STATE.CANCEL_REQUESTED, TASK_STATE.CANCELLED],
  [TASK_STATE.STAMPED]: [TASK_STATE.DISPATCHED, TASK_STATE.CANCEL_REQUESTED, TASK_STATE.CANCELLED],
  [TASK_STATE.DISPATCHED]: [TASK_STATE.IN_FLIGHT, TASK_STATE.FAILED, TASK_STATE.CANCEL_REQUESTED],
  [TASK_STATE.IN_FLIGHT]: [TASK_STATE.RESULT_RECEIVED, TASK_STATE.FAILED, TASK_STATE.CANCEL_REQUESTED],
  [TASK_STATE.RESULT_RECEIVED]: [TASK_STATE.VERIFIED, TASK_STATE.FAILED, TASK_STATE.QUESTION],
  [TASK_STATE.VERIFIED]: [TASK_STATE.CLOSED, TASK_STATE.FAILED],
  [TASK_STATE.QUESTION]: [TASK_STATE.NEGOTIATING, TASK_STATE.CANCELLED],
  [TASK_STATE.CONFLICT]: [TASK_STATE.NEGOTIATING, TASK_STATE.BLOCKED, TASK_STATE.CANCELLED],
  [TASK_STATE.BLOCKED]: [TASK_STATE.PROPOSED, TASK_STATE.CANCELLED],
  [TASK_STATE.HUMAN_GATE]: [TASK_STATE.APPROVED_FOR_DISPATCH, TASK_STATE.CANCELLED],
  [TASK_STATE.CANCEL_REQUESTED]: [TASK_STATE.CANCELLED, TASK_STATE.FAILED],
  [TASK_STATE.CANCELLED]: [],
  [TASK_STATE.CLOSED]: [],
  [TASK_STATE.FAILED]: []
};

class TaskStampRegistry {
  constructor(storageDir = null) {
    this.storageDir = storageDir;
    this.tasks = new Map(); // taskId -> Task
    this.writerLeases = new Map(); // scopePath -> activeTaskId
    this.history = []; // audit log
    if (this.storageDir) {
      if (!fs.existsSync(this.storageDir)) {
        fs.mkdirSync(this.storageDir, { recursive: true });
      }
      this.stateFile = path.join(this.storageDir, 'task_stamp_state.json');
      this._load();
    }
  }

  _load() {
    if (this.stateFile && fs.existsSync(this.stateFile)) {
      try {
        const raw = JSON.parse(fs.readFileSync(this.stateFile, 'utf8'));
        if (raw.tasks) {
          for (const [id, t] of Object.entries(raw.tasks)) this.tasks.set(id, t);
        }
        if (raw.writerLeases) {
          for (const [scope, id] of Object.entries(raw.writerLeases)) this.writerLeases.set(scope, id);
        }
        if (raw.history) {
          this.history = raw.history;
        }
      } catch (err) {}
    }
  }

  _persist() {
    if (!this.stateFile) return;
    const data = {
      tasks: Object.fromEntries(this.tasks),
      writerLeases: Object.fromEntries(this.writerLeases),
      history: this.history
    };
    fs.writeFileSync(this.stateFile, JSON.stringify(data, null, 2), 'utf8');
  }

  static computeScopeFingerprint(scopePaths = []) {
    const sorted = Array.from(new Set(scopePaths)).sort();
    return crypto.createHash('sha256').update(sorted.join('|')).digest('hex');
  }

  static computeTaskFingerprint(task) {
    const payload = {
      task_id: task.task_id,
      version: task.version,
      goal_id: task.goal_id,
      command: task.command,
      scope_fingerprint: task.scope_fingerprint,
      acceptance_criteria: task.acceptance_criteria
    };
    return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  }

  getTask(taskId) {
    return this.tasks.get(taskId) || null;
  }

  getAllTasks() {
    return Array.from(this.tasks.values());
  }

  proposeTask({
    task_id,
    goal_id,
    version = 1,
    command,
    scope_paths = [],
    acceptance_criteria = [],
    supersedes = null
  }) {
    if (!task_id || !goal_id) throw new Error('[TASK_ERROR] task_id and goal_id are required');
    if (this.tasks.has(task_id)) {
      const existing = this.tasks.get(task_id);
      if (existing.version >= version) {
        throw new Error(`[TASK_ERROR] Task ${task_id} already exists with version ${existing.version}`);
      }
    }

    const scope_fingerprint = TaskStampRegistry.computeScopeFingerprint(scope_paths);
    const task = {
      task_id,
      goal_id,
      version,
      command,
      scope_paths: Array.from(new Set(scope_paths)),
      scope_fingerprint,
      acceptance_criteria,
      state: TASK_STATE.PROPOSED,
      worker_id: null,
      task_fingerprint: null,
      dispatched_at: null,
      supersedes,
      superseded_by: null,
      execution_uncertain: false,
      created_at: new Date().toISOString()
    };

    this.tasks.set(task_id, task);
    this._log(task_id, 'TASK_PROPOSED', { version, scope_paths });
    return task;
  }

  transition(taskId, targetState, meta = {}) {
    const task = this.tasks.get(taskId);
    if (!task) throw new Error(`[TASK_ERROR] Task ${taskId} not found`);

    const allowed = VALID_TRANSITIONS[task.state] || [];
    if (!allowed.includes(targetState)) {
      throw new Error(`[TRANSITION_ERROR] Cannot transition task ${taskId} from ${task.state} to ${targetState}`);
    }

    // State-specific actions
    if (targetState === TASK_STATE.STAMPED) {
      task.task_fingerprint = TaskStampRegistry.computeTaskFingerprint(task);
      task.stamped_at = new Date().toISOString();
    }

    if (targetState === TASK_STATE.DISPATCHED) {
      if (!task.worker_id) {
        task.worker_id = meta.worker_id || 'DEFAULT_WORKER';
      }
      task.dispatched_at = new Date().toISOString();
    }

    if (targetState === TASK_STATE.CLOSED || targetState === TASK_STATE.CANCELLED || targetState === TASK_STATE.FAILED) {
      this.releaseWriterLease(taskId);
    }

    const prevState = task.state;
    task.state = targetState;
    this._log(taskId, 'STATE_TRANSITION', { from: prevState, to: targetState, meta });
    return task;
  }

  acquireWriterLease(taskId) {
    const task = this.tasks.get(taskId);
    if (!task) throw new Error(`[TASK_ERROR] Task ${taskId} not found`);

    for (const scope of task.scope_paths) {
      const activeHolder = this.writerLeases.get(scope);
      if (activeHolder && activeHolder !== taskId) {
        const holderTask = this.tasks.get(activeHolder);
        if (holderTask && holderTask.state !== TASK_STATE.CLOSED && holderTask.state !== TASK_STATE.CANCELLED) {
          return {
            acquired: false,
            action: 'HOLD',
            conflicting_scope: scope,
            conflicting_task_id: activeHolder,
            reason: `Scope path '${scope}' is currently locked by in-flight task '${activeHolder}'`
          };
        }
      }
    }

    // Acquire all scopes
    for (const scope of task.scope_paths) {
      this.writerLeases.set(scope, taskId);
    }

    this._log(taskId, 'WRITER_LEASE_ACQUIRED', { scopes: task.scope_paths });
    return {
      acquired: true,
      action: 'PROCEED',
      scopes: task.scope_paths
    };
  }

  releaseWriterLease(taskId) {
    const task = this.tasks.get(taskId);
    if (!task) return;
    for (const scope of task.scope_paths) {
      if (this.writerLeases.get(scope) === taskId) {
        this.writerLeases.delete(scope);
      }
    }
    this._log(taskId, 'WRITER_LEASE_RELEASED', { scopes: task.scope_paths });
  }

  mutateTaskDefinition(taskId, patch) {
    const task = this.tasks.get(taskId);
    if (!task) throw new Error(`[TASK_ERROR] Task ${taskId} not found`);

    // Invariant: Once STAMPED or DISPATCHED, task definition is strictly immutable
    const immutableStates = [
      TASK_STATE.STAMPED,
      TASK_STATE.DISPATCHED,
      TASK_STATE.IN_FLIGHT,
      TASK_STATE.RESULT_RECEIVED,
      TASK_STATE.VERIFIED,
      TASK_STATE.CLOSED
    ];

    if (immutableStates.includes(task.state)) {
      throw new Error(`[IMMUTABILITY_ERROR] Task ${taskId} is ${task.state} and cannot be mutated. Create a superseding version.`);
    }

    Object.assign(task, patch);
    task.scope_fingerprint = TaskStampRegistry.computeScopeFingerprint(task.scope_paths);
    this._log(taskId, 'TASK_MUTATED', { patch });
    return task;
  }

  createSupersedingVersion(oldTaskId, newProps = {}) {
    const old = this.tasks.get(oldTaskId);
    if (!old) throw new Error(`[TASK_ERROR] Task ${oldTaskId} not found`);

    const newVersion = old.version + 1;
    const newTaskId = `${old.task_id}_v${newVersion}`;

    const newTask = this.proposeTask({
      task_id: newTaskId,
      goal_id: old.goal_id,
      version: newVersion,
      command: newProps.command || old.command,
      scope_paths: newProps.scope_paths || old.scope_paths,
      acceptance_criteria: newProps.acceptance_criteria || old.acceptance_criteria,
      supersedes: old.task_id
    });

    old.superseded_by = newTaskId;
    this._log(oldTaskId, 'TASK_SUPERSEDED', { by: newTaskId });
    return newTask;
  }

  markExecutionUncertain(taskId, reason) {
    const task = this.tasks.get(taskId);
    if (!task) throw new Error(`[TASK_ERROR] Task ${taskId} not found`);

    task.execution_uncertain = true;
    this._log(taskId, 'EXECUTION_UNCERTAIN', { reason });
  }

  canCreateReplacementDispatch(taskId) {
    const task = this.tasks.get(taskId);
    if (!task) return false;

    // Critical Invariant: If task is in EXECUTION_UNCERTAIN state, replacement dispatch is strictly blocked
    if (task.execution_uncertain) {
      return {
        allowed: false,
        action: 'BLOCK_REPLACEMENT_DISPATCH',
        reason: 'Execution outcome is uncertain. Replacement dispatch forbidden without human gate.'
      };
    }

    return { allowed: true, action: 'ALLOW_DISPATCH' };
  }

  _log(taskId, event, details = {}) {
    this.history.push({
      timestamp: new Date().toISOString(),
      task_id: taskId,
      event,
      details
    });
    this._persist();
  }
}

module.exports = {
  TASK_STATE,
  VALID_TRANSITIONS,
  TaskStampRegistry,
  TaskStampManager: TaskStampRegistry
};
