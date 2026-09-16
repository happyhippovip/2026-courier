// Supervisor Plane (12 states) & Execution Uncertainty & Follow-up Inbox
const SUPERVISOR_STATES = Object.freeze({
  STARTING: 'STARTING',
  RUNNING: 'RUNNING',
  WAITING_VALID: 'WAITING_VALID',
  PROGRESSING: 'PROGRESSING',
  STALLED: 'STALLED',
  HUNG: 'HUNG',
  ORPHANED: 'ORPHANED',
  DUPLICATE: 'DUPLICATE',
  EXECUTION_UNCERTAIN: 'EXECUTION_UNCERTAIN',
  COMPLETED: 'COMPLETED',
  TERMINATED: 'TERMINATED',
  HUMAN_GATE: 'HUMAN_GATE'
});

class SupervisorPlane {
  constructor() {
    this.processStates = new Map(); // pid -> stateRec
  }

  assessProcessHealth(pid, { lastActivityMs, isResponsive, isAlive }) {
    if (!isAlive) {
      return { state: SUPERVISOR_STATES.TERMINATED, action: 'CLEANUP' };
    }
    const inactiveSec = (Date.now() - lastActivityMs) / 1000;
    
    // 5 minutes (300s): Check progress
    if (inactiveSec > 300 && inactiveSec <= 900) {
      return { state: SUPERVISOR_STATES.STALLED, action: 'CHECK_PROGRESS', diagnostic_required: false };
    }
    // 15 minutes (900s): Capture diagnostic
    if (inactiveSec > 900) {
      return { state: SUPERVISOR_STATES.HUNG, action: 'CAPTURE_DIAGNOSTIC_AND_EVALUATE', diagnostic_required: true };
    }
    return { state: SUPERVISOR_STATES.PROGRESSING, action: 'CONTINUE' };
  }
}

class ExecutionUncertaintyManager {
  constructor() {
    this.fencedTasks = new Map(); // taskId -> record
  }

  fenceTask(taskId, reason) {
    const rec = {
      task_id: taskId,
      fenced_at: new Date().toISOString(),
      reason,
      state: 'EXECUTION_UNCERTAIN_NO_PROOF',
      auto_redispatch_allowed: false
    };
    this.fencedTasks.set(taskId, rec);
    return rec;
  }

  isFenced(taskId) {
    return this.fencedTasks.has(taskId);
  }
}

class FollowUpInbox {
  constructor() {
    this.inbox = [];
  }

  capture({ title, description, priority = 'P2', sourceTaskId = null, tags = [] }) {
    const item = {
      idea_id: `IDEA-${Date.now()}-${this.inbox.length + 1}`,
      title,
      description,
      priority,
      source_task_id: sourceTaskId,
      tags,
      status: 'CAPTURED',
      captured_at: new Date().toISOString()
    };
    this.inbox.push(item);
    return item;
  }

  promoteToCandidate(ideaId) {
    const item = this.inbox.find(i => i.idea_id === ideaId);
    if (item) item.status = 'CANDIDATE';
    return item;
  }

  getAll() {
    return this.inbox;
  }
}

module.exports = {
  SupervisorPlane,
  SUPERVISOR_STATES,
  ExecutionUncertaintyManager,
  FollowUpInbox
};
