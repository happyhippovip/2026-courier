// State Projector: Transforms append-only event stream into derived state snapshot
class StateProjector {
  constructor() {
    this.goals = new Map();
    this.tasks = new Map();
    this.leases = new Map();
    this.processes = new Map();
    this.followUps = [];
    this.fencedTasks = new Set();
    this.evidence = [];
    this.lastSequence = 0;
  }

  project(event) {
    this.lastSequence++;
    switch (event.type) {
      case 'GOAL_CREATED':
      case 'GOAL_UPDATED':
        if (event.goal) {
          this.goals.set(event.goal.goal_id, { ...event.goal, updated_at: event.timestamp });
        }
        break;
      case 'GOAL_SATISFIED':
        if (this.goals.has(event.goal_id)) {
          this.goals.get(event.goal_id).status = 'SATISFIED';
          this.goals.get(event.goal_id).satisfied_at = event.timestamp;
        }
        break;
      case 'TASK_PROPOSED':
        if (event.task) {
          this.tasks.set(event.task.task_id, { ...event.task, state: 'PROPOSED' });
        }
        break;
      case 'TASK_NEGOTIATED':
      case 'TASK_STAMPED':
      case 'TASK_DISPATCHED':
      case 'TASK_COMPLETED':
      case 'TASK_VERIFIED':
      case 'TASK_CLOSED': {
        const tid = event.task_id || (event.task && event.task.task_id);
        if (tid) {
          const existing = this.tasks.get(tid) || {};
          const newState = event.type.replace('TASK_', '');
          this.tasks.set(tid, { ...existing, task_id: tid, state: newState, updated_at: event.timestamp });
        }
        break;
      }
      case 'TASK_FENCED':
        this.fencedTasks.add(event.task_id);
        if (this.tasks.has(event.task_id)) {
          this.tasks.get(event.task_id).state = 'EXECUTION_UNCERTAIN';
        }
        break;
      case 'LEASE_ACQUIRED':
        this.leases.set(event.resource, { taskId: event.task_id, mode: event.mode || 'EXCL', acquiredAt: event.timestamp });
        break;
      case 'LEASE_RELEASED':
        this.leases.delete(event.resource);
        break;
      case 'PROCESS_REGISTERED':
        this.processes.set(event.pid, { pid: event.pid, startTime: event.start_time, taskToken: event.task_token, status: 'ACTIVE' });
        break;
      case 'PROCESS_TERMINATED':
        this.processes.delete(event.pid);
        break;
      case 'FOLLOW_UP_CAPTURED':
        this.followUps.push(event.follow_up);
        break;
      default:
        break;
    }
  }

  projectAll(events) {
    events.forEach(e => this.project(e));
    return this.getSnapshot();
  }

  getSnapshot() {
    return {
      goals: Array.from(this.goals.values()),
      tasks: Array.from(this.tasks.values()),
      active_leases: Array.from(this.leases.entries()).map(([k, v]) => ({ resource: k, ...v })),
      active_processes: Array.from(this.processes.values()),
      fenced_tasks: Array.from(this.fencedTasks),
      follow_ups: this.followUps,
      sequence_number: this.lastSequence
    };
  }
}

module.exports = { StateProjector };
