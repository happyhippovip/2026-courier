// Task Store with 9-State Lifecycle Machine & 10 Worker Negotiation Responses
const crypto = require('crypto');

const TASK_LIFECYCLE_STATES = Object.freeze({
  PROPOSED: 'PROPOSED',
  NEGOTIATING: 'NEGOTIATING',
  APPROVED_FOR_DISPATCH: 'APPROVED_FOR_DISPATCH',
  STAMPED: 'STAMPED',
  DISPATCHED: 'DISPATCHED',
  IN_FLIGHT: 'IN_FLIGHT',
  RESULT_RECEIVED: 'RESULT_RECEIVED',
  VERIFIED: 'VERIFIED',
  CLOSED: 'CLOSED'
});

const ALTERNATIVE_TASK_STATES = Object.freeze({
  QUESTION: 'QUESTION',
  CONFLICT: 'CONFLICT',
  BLOCKED: 'BLOCKED',
  HUMAN_GATE: 'HUMAN_GATE',
  CANCEL_REQUESTED: 'CANCEL_REQUESTED',
  CANCELLED: 'CANCELLED',
  FAILED: 'FAILED',
  EXECUTION_UNCERTAIN: 'EXECUTION_UNCERTAIN'
});

const NEGOTIATION_RESPONSES = Object.freeze([
  'ACCEPT',
  'QUESTION',
  'CONFLICT',
  'NEEDS_SCOPE_CHANGE',
  'BETTER_ALTERNATIVE',
  'INSUFFICIENT_EVIDENCE',
  'UNSAFE',
  'DUPLICATE_WORK',
  'ALREADY_DONE',
  'UNAVAILABLE'
]);

class TaskStore {
  constructor() {
    this.tasks = new Map();
  }

  createTask({ task_id, title, priority = 'P1', goal_id, working_dir, required_capability = 'WORKSPACE_WRITE', scope_paths = [], payload = {} }) {
    const fingerprint = crypto.createHash('sha256').update(`${task_id}:${working_dir}:${JSON.stringify(payload)}`).digest('hex');
    const task = {
      task_id,
      task_version: 1, version: 1,
      title,
      priority,
      goal_id,
      working_dir,
      required_capability,
      scope_paths: scope_paths.length > 0 ? scope_paths : [working_dir],
      fingerprint,
      payload,
      state: TASK_LIFECYCLE_STATES.PROPOSED,
      created_at: new Date().toISOString(),
      history: [{ state: TASK_LIFECYCLE_STATES.PROPOSED, timestamp: new Date().toISOString() }]
    };
    this.tasks.set(task_id, task);
    return task;
  }

  transition(task_id, newState, reason = '') {
    const task = this.tasks.get(task_id);
    if (!task) throw new Error('Task not found: ' + task_id);
    task.state = newState;
    task.history.push({ state: newState, reason, timestamp: new Date().toISOString() });
    return task;
  }

  getTask(task_id) {
    return this.tasks.get(task_id);
  }
}

class TaskNegotiator {
  static evaluateWorkerResponse(task, workerResponse) {
    if (!NEGOTIATION_RESPONSES.includes(workerResponse.type)) {
      throw new Error('Invalid negotiation response type: ' + workerResponse.type);
    }

    switch (workerResponse.type) {
      case 'ACCEPT':
        return { action: 'PROCEED_TO_STAMP', task_id: task.task_id, next_state: TASK_LIFECYCLE_STATES.APPROVED_FOR_DISPATCH };
      case 'QUESTION':
      case 'NEEDS_SCOPE_CHANGE':
      case 'BETTER_ALTERNATIVE':
        return { action: 'REVISE_TASK_PROPOSAL', task_id: task.task_id, details: workerResponse.details, next_state: TASK_LIFECYCLE_STATES.NEGOTIATING };
      case 'CONFLICT':
      case 'DUPLICATE_WORK':
      case 'ALREADY_DONE':
        return { action: 'DEFER_OR_SUPERSEDE', task_id: task.task_id, details: workerResponse.details, next_state: ALTERNATIVE_TASK_STATES.CONFLICT };
      case 'UNSAFE':
        return { action: 'CANCEL_UNSAFE', task_id: task.task_id, details: workerResponse.details, next_state: ALTERNATIVE_TASK_STATES.CANCELLED };
      case 'UNAVAILABLE':
      case 'INSUFFICIENT_EVIDENCE':
        return { action: 'QUEUE_DEPENDENCY', task_id: task.task_id, next_state: ALTERNATIVE_TASK_STATES.BLOCKED };
      default:
        return { action: 'HOLD', task_id: task.task_id };
    }
  }
}

module.exports = {
  TaskStore,
  TaskNegotiator,
  TASK_LIFECYCLE_STATES,
  ALTERNATIVE_TASK_STATES,
  NEGOTIATION_RESPONSES
};
