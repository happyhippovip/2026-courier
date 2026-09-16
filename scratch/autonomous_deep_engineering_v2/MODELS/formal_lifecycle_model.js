/**
 * FORMAL LIFECYCLE INVARIANT MODEL (V2 LAB)
 * 
 * Formal state transition engine for:
 * GOAL, MISSION, TASK, TASK_VERSION, WORKER, LEASE, PROCESS,
 * DISPATCH, RESULT, VERIFICATION, FOLLOW_UP, BORDER_DECISION, HUMAN_GATE, TERMINAL_STATE.
 */

const crypto = require('crypto');

const LIFECYCLE_STATES = Object.freeze({
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

// Explicit, canonical graph of allowed state transitions
const LEGAL_TRANSITION_GRAPH = Object.freeze({
  [LIFECYCLE_STATES.PROPOSED]: [
    LIFECYCLE_STATES.NEGOTIATING,
    LIFECYCLE_STATES.QUESTION,
    LIFECYCLE_STATES.CONFLICT,
    LIFECYCLE_STATES.BLOCKED,
    LIFECYCLE_STATES.CANCELLED
  ],
  [LIFECYCLE_STATES.NEGOTIATING]: [
    LIFECYCLE_STATES.APPROVED_FOR_DISPATCH,
    LIFECYCLE_STATES.QUESTION,
    LIFECYCLE_STATES.CONFLICT,
    LIFECYCLE_STATES.BLOCKED,
    LIFECYCLE_STATES.CANCELLED
  ],
  [LIFECYCLE_STATES.APPROVED_FOR_DISPATCH]: [
    LIFECYCLE_STATES.STAMPED,
    LIFECYCLE_STATES.HUMAN_GATE,
    LIFECYCLE_STATES.CANCEL_REQUESTED,
    LIFECYCLE_STATES.CANCELLED
  ],
  [LIFECYCLE_STATES.STAMPED]: [
    LIFECYCLE_STATES.DISPATCHED,
    LIFECYCLE_STATES.CANCEL_REQUESTED,
    LIFECYCLE_STATES.CANCELLED
  ],
  [LIFECYCLE_STATES.DISPATCHED]: [
    LIFECYCLE_STATES.IN_FLIGHT,
    LIFECYCLE_STATES.FAILED,
    LIFECYCLE_STATES.CANCEL_REQUESTED
  ],
  [LIFECYCLE_STATES.IN_FLIGHT]: [
    LIFECYCLE_STATES.RESULT_RECEIVED,
    LIFECYCLE_STATES.FAILED,
    LIFECYCLE_STATES.CANCEL_REQUESTED
  ],
  [LIFECYCLE_STATES.RESULT_RECEIVED]: [
    LIFECYCLE_STATES.VERIFIED,
    LIFECYCLE_STATES.FAILED,
    LIFECYCLE_STATES.QUESTION
  ],
  [LIFECYCLE_STATES.VERIFIED]: [
    LIFECYCLE_STATES.CLOSED,
    LIFECYCLE_STATES.FAILED
  ],
  [LIFECYCLE_STATES.CLOSED]: [], // Terminal
  [LIFECYCLE_STATES.QUESTION]: [
    LIFECYCLE_STATES.NEGOTIATING,
    LIFECYCLE_STATES.CANCELLED
  ],
  [LIFECYCLE_STATES.CONFLICT]: [
    LIFECYCLE_STATES.NEGOTIATING,
    LIFECYCLE_STATES.BLOCKED,
    LIFECYCLE_STATES.CANCELLED
  ],
  [LIFECYCLE_STATES.BLOCKED]: [
    LIFECYCLE_STATES.PROPOSED,
    LIFECYCLE_STATES.CANCELLED
  ],
  [LIFECYCLE_STATES.HUMAN_GATE]: [
    LIFECYCLE_STATES.APPROVED_FOR_DISPATCH,
    LIFECYCLE_STATES.CANCELLED
  ],
  [LIFECYCLE_STATES.CANCEL_REQUESTED]: [
    LIFECYCLE_STATES.CANCELLED,
    LIFECYCLE_STATES.FAILED
  ],
  [LIFECYCLE_STATES.CANCELLED]: [], // Terminal
  [LIFECYCLE_STATES.FAILED]: []    // Terminal
});

class FormalLifecycleModel {
  constructor() {
    this.tasks = new Map();
  }

  createTask({
    task_id,
    goal_id,
    mission_id = 'DEFAULT_MISSION',
    version = 1,
    command = 'test',
    scope_paths = []
  }) {
    if (!task_id || !goal_id) throw new Error('[LIFECYCLE_ERROR] task_id and goal_id required');
    const task = {
      task_id,
      goal_id,
      mission_id,
      version,
      command,
      scope_paths,
      state: LIFECYCLE_STATES.PROPOSED,
      execution_uncertain: false,
      result_fingerprint: null,
      verification_ref: null,
      history: [{ from: null, to: LIFECYCLE_STATES.PROPOSED, timestamp: new Date().toISOString() }]
    };
    this.tasks.set(task_id, task);
    return task;
  }

  evaluateTransition(task_id, targetState, context = {}) {
    const task = this.tasks.get(task_id);
    if (!task) return { allowed: false, code: 'ERR_TASK_NOT_FOUND', reason: `Task ${task_id} does not exist` };

    const currentState = task.state;
    const allowedTargets = LEGAL_TRANSITION_GRAPH[currentState] || [];

    // 1. Basic Graph Transition Legality
    if (!allowedTargets.includes(targetState)) {
      return {
        allowed: false,
        code: 'ERR_ILLEGAL_TRANSITION',
        reason: `Direct transition from ${currentState} to ${targetState} is strictly forbidden by formal lifecycle grammar`
      };
    }

    // 2. Specific Semantic Invariants
    // Invariant A: Cannot stamp without fingerprintable task definition
    if (targetState === LIFECYCLE_STATES.STAMPED) {
      if (!task.command || !task.scope_paths || task.scope_paths.length === 0) {
        return { allowed: false, code: 'ERR_UNSTAMPABLE', reason: 'Task definition missing command or scope_paths' };
      }
    }

    // Invariant B: Cannot dispatch if execution_uncertain
    if (targetState === LIFECYCLE_STATES.DISPATCHED) {
      if (task.execution_uncertain) {
        return { allowed: false, code: 'ERR_EXECUTION_UNCERTAIN', reason: 'Task marked EXECUTION_UNCERTAIN: redispatch forbidden' };
      }
      if (!context.worker_id) {
        return { allowed: false, code: 'ERR_MISSING_WORKER', reason: 'Worker ID required for dispatch' };
      }
    }

    // Invariant C: Cannot verify without result evidence
    if (targetState === LIFECYCLE_STATES.VERIFIED) {
      if (!context.verification_evidence || !context.result_fingerprint) {
        return { allowed: false, code: 'ERR_UNVERIFIED_RESULT', reason: 'Verification requires result fingerprint and independent evidence' };
      }
    }

    // Invariant D: Cannot close from RESULT_RECEIVED directly without VERIFIED
    if (currentState === LIFECYCLE_STATES.RESULT_RECEIVED && targetState === LIFECYCLE_STATES.CLOSED) {
      return { allowed: false, code: 'ERR_UNVERIFIED_CLOSE', reason: 'Result received must pass VERIFIED before CLOSED' };
    }

    // Invariant E: Human gate must have explicit operator clearance
    if (currentState === LIFECYCLE_STATES.HUMAN_GATE && targetState === LIFECYCLE_STATES.APPROVED_FOR_DISPATCH) {
      if (!context.human_approval_signature) {
        return { allowed: false, code: 'ERR_GATE_NOT_CLEARED', reason: 'Human gate requires explicit approval signature' };
      }
    }

    return { allowed: true, code: 'ALLOW', reason: 'Transition satisfies formal invariant grammar' };
  }

  executeTransition(task_id, targetState, context = {}) {
    const evalResult = this.evaluateTransition(task_id, targetState, context);
    if (!evalResult.allowed) {
      throw new Error(`[LIFECYCLE_VIOLATION:${evalResult.code}] ${evalResult.reason}`);
    }
    const task = this.tasks.get(task_id);
    const prevState = task.state;
    task.state = targetState;
    if (context.result_fingerprint) task.result_fingerprint = context.result_fingerprint;
    if (context.verification_evidence) task.verification_ref = context.verification_evidence;
    task.history.push({ from: prevState, to: targetState, timestamp: new Date().toISOString(), context });
    return task;
  }
}

module.exports = {
  LIFECYCLE_STATES,
  LEGAL_TRANSITION_GRAPH,
  FormalLifecycleModel
};
