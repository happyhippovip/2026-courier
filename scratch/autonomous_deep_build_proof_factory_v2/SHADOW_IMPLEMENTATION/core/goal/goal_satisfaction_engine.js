'use strict';

/**
 * GoalSatisfactionEngine
 * Manages the lifecycle of high-level goals and coordinates constituent tasks.
 */
class GoalSatisfactionEngine {
  constructor(options = {}) {
    this.verifier = options.verifier || null;
    this.goals = new Map(); // goal_id -> goal object
    this.tasks = new Map(); // task_id -> task object
    this.clearedDeliverables = new Map(); // path -> artifact info
  }

  createGoal(spec) {
    if (!spec || !spec.goal_id) {
      throw new Error('Goal specification must include goal_id');
    }
    const goal = {
      goal_id: spec.goal_id,
      description: spec.description || '',
      acceptance_criteria: spec.acceptance_criteria || [],
      status: 'CREATED',
      constituent_tasks: [],
      created_at_ms: Date.now(),
      supersedes_goal_id: spec.supersedes_goal_id || null,
      superseded_by_goal_id: null
    };
    this.goals.set(goal.goal_id, goal);
    return goal;
  }

  addTaskToGoal(goalId, taskSpec) {
    const goal = this.goals.get(goalId);
    if (!goal) throw new Error(`Goal ${goalId} not found`);
    if (goal.status === 'SUPERSEDED') {
      throw new Error(`Cannot add task to SUPERSEDED goal ${goalId}`);
    }

    const task = {
      task_id: taskSpec.task_id,
      goal_id: goalId,
      status: 'READY',
      proof_package: null,
      artifacts: [],
      created_at_ms: Date.now()
    };
    this.tasks.set(task.task_id, task);
    goal.constituent_tasks.push(task.task_id);

    if (goal.status === 'CREATED' || goal.status === 'PLANNING') {
      goal.status = 'DISPATCHED';
    }
    return task;
  }

  updateTaskStatus(taskId, status, details = {}) {
    const task = this.tasks.get(taskId);
    if (!task) throw new Error(`Task ${taskId} not found`);
    const goal = this.goals.get(task.goal_id);
    if (!goal) throw new Error(`Parent goal ${task.goal_id} not found`);

    if (goal.status === 'SUPERSEDED') {
      throw new Error(`Execution rejected: Parent goal ${goal.goal_id} is SUPERSEDED`);
    }

    task.status = status;
    if (details.proof_package) task.proof_package = details.proof_package;
    if (details.artifacts) {
      task.artifacts = details.artifacts;
      for (const art of details.artifacts) {
        this.clearedDeliverables.set(art.path, art);
      }
    }

    this._reevaluateGoalProgress(goal);
    return task;
  }

  _reevaluateGoalProgress(goal) {
    const tasks = goal.constituent_tasks.map(id => this.tasks.get(id)).filter(Boolean);
    const total = tasks.length;
    if (total === 0) return;

    const completed = tasks.filter(t => t.status === 'CLOSED_SUCCESS').length;
    const failed = tasks.filter(t => t.status === 'CLOSED_FAILED' || t.status === 'FATAL').length;
    const allTerminal = tasks.every(t => t.status.startsWith('CLOSED_') || t.status === 'FATAL' || t.status === 'SUPERSEDED_CANCELLED');

    if (completed === total) {
      goal.status = 'VERIFYING';
    } else if (allTerminal && failed > 0) {
      goal.status = 'BLOCKED';
    } else if (completed > 0) {
      goal.status = 'PARTIALLY_SATISFIED';
    } else if (failed > 0) {
      goal.status = 'BLOCKED';
    }
  }

  requestGoalVerification(goalId) {
    const goal = this.goals.get(goalId);
    if (!goal) throw new Error(`Goal ${goalId} not found`);
    if (goal.status === 'SUPERSEDED') {
      throw new Error(`Cannot verify SUPERSEDED goal ${goalId}`);
    }

    if (!this.verifier) {
      throw new Error('Independent GoalVerifier is required for satisfaction verdict');
    }

    const tasks = goal.constituent_tasks.map(id => this.tasks.get(id)).filter(Boolean);
    const verdict = this.verifier.verifyGoal(goal, tasks, this.clearedDeliverables);

    if (verdict.satisfied) {
      goal.status = 'SATISFIED';
      goal.satisfied_at_ms = Date.now();
      return { success: true, goal_status: 'SATISFIED', verdict };
    } else {
      goal.status = 'BLOCKED';
      return { success: false, goal_status: 'BLOCKED', verdict };
    }
  }

  supersedeGoal(oldGoalId, newGoalSpec) {
    const oldGoal = this.goals.get(oldGoalId);
    if (!oldGoal) throw new Error(`Goal ${oldGoalId} not found`);

    // Transition old goal to SUPERSEDED
    oldGoal.status = 'SUPERSEDED';
    oldGoal.superseded_at_ms = Date.now();

    // Drain / cancel in-flight tasks
    for (const taskId of oldGoal.constituent_tasks) {
      const t = this.tasks.get(taskId);
      if (t && (t.status === 'READY' || t.status === 'DISPATCHED' || t.status === 'IN_PROGRESS')) {
        t.status = 'SUPERSEDED_CANCELLED';
      }
    }

    // Mark historical deliverables
    for (const taskId of oldGoal.constituent_tasks) {
      const t = this.tasks.get(taskId);
      if (t && t.artifacts) {
        for (const art of t.artifacts) {
          art.historical_tag = 'SUPERSEDED_HISTORICAL';
        }
      }
    }

    // Create new goal V2
    const newGoal = this.createGoal({
      ...newGoalSpec,
      supersedes_goal_id: oldGoalId
    });
    oldGoal.superseded_by_goal_id = newGoal.goal_id;

    return newGoal;
  }
}

module.exports = { GoalSatisfactionEngine };
