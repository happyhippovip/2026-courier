'use strict';

/**
 * GoalVerifier
 * Independent auditor for goal satisfaction.
 * Enforces that a goal cannot declare its own completion; an external,
 * independent verification must inspect all deliverables and criteria.
 */
class GoalVerifier {
  constructor(options = {}) {
    this.customs = options.customs || null;
  }

  verifyGoal(goal, tasks = [], clearedDeliverables = new Map()) {
    if (!goal || typeof goal !== 'object') {
      return { satisfied: false, reason: 'INVALID_GOAL_OBJECT' };
    }

    if (!Array.isArray(tasks) || tasks.length === 0) {
      return { satisfied: false, reason: 'ZERO_TASKS_CANNOT_SATISFY_GOAL' };
    }

    const unmetCriteria = [];
    const taskMap = new Map(tasks.map(t => [t.task_id, t]));

    // 1. Check all linked tasks are CLOSED_SUCCESS
    for (const task of tasks) {
      if (task.goal_id !== goal.goal_id) {
        return { satisfied: false, reason: 'TASK_GOAL_ID_MISMATCH', detail: `Task ${task.task_id} belongs to ${task.goal_id}, not ${goal.goal_id}` };
      }
      if (task.status !== 'CLOSED_SUCCESS') {
        unmetCriteria.push(`TASK_NOT_SUCCESS: ${task.task_id} is in status ${task.status}`);
      }
    }

    // 2. Check acceptance criteria
    const criteria = goal.acceptance_criteria || [];
    if (criteria.length === 0) {
      unmetCriteria.push('NO_ACCEPTANCE_CRITERIA_DEFINED');
    }

    for (const c of criteria) {
      if (c.type === 'ASSERTIONS_MIN') {
        let totalAssertions = 0;
        for (const t of tasks) {
          if (t.proof_package && typeof t.proof_package.assertions_run === 'number') {
            totalAssertions += t.proof_package.assertions_run;
          }
        }
        if (totalAssertions < c.threshold) {
          unmetCriteria.push(`ASSERTIONS_THRESHOLD_UNMET: required ${c.threshold}, got ${totalAssertions}`);
        }
      } else if (c.type === 'DELIVERABLE_EXISTS') {
        const found = clearedDeliverables.has(c.artifact_path);
        if (!found) {
          unmetCriteria.push(`DELIVERABLE_MISSING: ${c.artifact_path}`);
        }
      } else if (c.type === 'CUSTOM') {
        if (typeof c.fn === 'function') {
          const pass = c.fn(tasks, clearedDeliverables);
          if (!pass) {
            unmetCriteria.push(`CUSTOM_CRITERIA_FAILED: ${c.criteria_id}`);
          }
        }
      }
    }

    const satisfied = unmetCriteria.length === 0;

    return {
      satisfied,
      reason: satisfied ? 'ALL_CRITERIA_SATISFIED' : 'CRITERIA_UNMET',
      unmet_criteria: unmetCriteria,
      total_tasks: tasks.length,
      verified_at_ms: Date.now()
    };
  }
}

module.exports = { GoalVerifier };
