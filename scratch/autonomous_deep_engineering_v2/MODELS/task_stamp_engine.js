/**
 * TASK STAMP IMMUTABILITY ENGINE (V2 LAB)
 * 
 * Formal contract enforcing:
 * Task definition is strictly immutable once STAMPED.
 * Any update requires an explicit superseding task version.
 */

const crypto = require('crypto');

class TaskStampEngine {
  constructor() {
    this.registry = new Map();
  }

  createTask(def) {
    const task = {
      task_id: def.task_id,
      goal_id: def.goal_id,
      version: def.version || 1,
      command: def.command,
      scope_paths: Array.from(new Set(def.scope_paths || [])).sort(),
      acceptance_criteria: Array.from(new Set(def.acceptance_criteria || [])).sort(),
      assigned_worker_id: def.assigned_worker_id || null,
      is_writer: def.is_writer !== undefined ? def.is_writer : true,
      risk_class: def.risk_class || 'NORMAL',
      human_gates: def.human_gates || [],
      required_evidence: def.required_evidence || ['test_logs'],
      state: 'PROPOSED',
      stamped_at: null,
      task_fingerprint: null,
      supersedes: def.supersedes || null,
      superseded_by: null
    };
    this.registry.set(task.task_id, task);
    return task;
  }

  stamp(taskId) {
    const task = this.registry.get(taskId);
    if (!task) throw new Error(`Task ${taskId} not found`);

    const payload = {
      task_id: task.task_id,
      goal_id: task.goal_id,
      version: task.version,
      command: task.command,
      scope_paths: task.scope_paths,
      acceptance_criteria: task.acceptance_criteria,
      is_writer: task.is_writer,
      risk_class: task.risk_class,
      human_gates: task.human_gates,
      required_evidence: task.required_evidence
    };

    task.task_fingerprint = crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
    task.stamped_at = new Date().toISOString();
    task.state = 'STAMPED';
    return task;
  }

  /**
   * Attempts in-place mutation of a task property.
   * STRICT INVARIANT: Fails if task is STAMPED or beyond.
   */
  attemptMutation(taskId, field, newValue) {
    const task = this.registry.get(taskId);
    if (!task) throw new Error(`Task ${taskId} not found`);

    const immutableStates = ['STAMPED', 'DISPATCHED', 'IN_FLIGHT', 'RESULT_RECEIVED', 'VERIFIED', 'CLOSED'];
    if (immutableStates.includes(task.state)) {
      throw new Error(`[IMMUTABILITY_ERROR] Field '${field}' cannot be mutated on task '${taskId}' because state is '${task.state}'. Superseding version required.`);
    }

    task[field] = newValue;
    return task;
  }

  /**
   * Safe, explicit version supersession.
   */
  supersedeTask(oldTaskId, delta = {}) {
    const old = this.registry.get(oldTaskId);
    if (!old) throw new Error(`Task ${oldTaskId} not found`);

    const newVersion = old.version + 1;
    const newTaskId = `${old.task_id}_v${newVersion}`;

    const newTask = this.createTask({
      task_id: newTaskId,
      goal_id: old.goal_id,
      version: newVersion,
      command: delta.command || old.command,
      scope_paths: delta.scope_paths || old.scope_paths,
      acceptance_criteria: delta.acceptance_criteria || old.acceptance_criteria,
      is_writer: delta.is_writer !== undefined ? delta.is_writer : old.is_writer,
      risk_class: delta.risk_class || old.risk_class,
      human_gates: delta.human_gates || old.human_gates,
      required_evidence: delta.required_evidence || old.required_evidence,
      supersedes: old.task_id
    });

    old.superseded_by = newTaskId;
    return newTask;
  }
}

module.exports = { TaskStampEngine };
