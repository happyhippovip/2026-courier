'use strict';

/**
 * SHADOW IMPLEMENTATION: DISPATCHER UNCERTAINTY FENCE (A01)
 * Component: shadow/core/dispatch/dispatcher_uncertainty_fence.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

class FatalExecutionUncertaintyBlocked extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'FatalExecutionUncertaintyBlocked';
    this.details = details;
  }
}

class DependencyCycleError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'DependencyCycleError';
    this.details = details;
  }
}

const ALL_TRIGGER_FAMILIES = Object.freeze([
  'RETRY',
  'FALLBACK',
  'REPLAN',
  'REROUTE',
  'RESTART_RECONCILIATION',
  'LEASE_EXPIRY',
  'SUPERVISOR_SWEEP',
  'RESOURCE_GOVERNOR',
  'MANUAL_WEITER',
  'WORKER_RECONNECT',
  'DEPENDENCY_CHILD',
  'SCHEDULED_RECOVERY',
  'DUPLICATE_QUEUE_ITEM',
  'STALE_CHECKPOINT'
]);

class DispatcherUncertaintyFence {
  constructor(options = {}) {
    this.uncertainTasks = new Map(); // taskId -> record
    this.uncertainLogicalWork = new Set(); // logicalWorkId
    this.dependencies = new Map(); // taskId -> Set of parentTaskIds
    this.taskStatuses = new Map(); // taskId -> status

    // Mutation test switches
    this.allowFallbackBypass = options.allowFallbackBypass || false;
    this.disablePropagation = options.disablePropagation || false;
  }

  registerDependency(childTaskId, parentTaskId) {
    if (!this.dependencies.has(childTaskId)) {
      this.dependencies.set(childTaskId, new Set());
    }
    this.dependencies.get(childTaskId).add(parentTaskId);
    this.detectCycles();
  }

  detectCycles() {
    const visited = new Set();
    const stack = new Set();

    const dfs = (node, path = []) => {
      visited.add(node);
      stack.add(node);
      path.push(node);

      const parents = this.dependencies.get(node) || [];
      for (const parent of parents) {
        if (!visited.has(parent)) {
          dfs(parent, [...path]);
        } else if (stack.has(parent)) {
          throw new DependencyCycleError(
            `Circular task dependency detected: ${path.join(' -> ')} -> ${parent}`,
            { cycle: [...path, parent] }
          );
        }
      }

      stack.delete(node);
    };

    for (const node of this.dependencies.keys()) {
      if (!visited.has(node)) {
        dfs(node);
      }
    }
  }

  markExecutionUncertain(taskDescriptor, reason = 'Unproven execution state on crash/disconnect') {
    const { task_id, logical_work_id } = taskDescriptor;
    const record = {
      task_id,
      logical_work_id,
      status: 'EXECUTION_UNCERTAIN',
      reason,
      marked_at: new Date().toISOString()
    };

    this.uncertainTasks.set(task_id, record);
    if (logical_work_id) {
      this.uncertainLogicalWork.add(logical_work_id);
    }
    this.taskStatuses.set(task_id, 'EXECUTION_UNCERTAIN');

    if (!this.disablePropagation) {
      this.propagateUncertainty(task_id);
    }

    return record;
  }

  propagateUncertainty(rootTaskId) {
    const queue = [rootTaskId];
    const visited = new Set([rootTaskId]);

    while (queue.length > 0) {
      const current = queue.shift();

      // Find all children that depend on current
      for (const [childId, parentSet] of this.dependencies.entries()) {
        if (parentSet.has(current)) {
          this.taskStatuses.set(childId, 'BLOCKED_DEPENDENT_UNCERTAIN');
          if (!visited.has(childId)) {
            visited.add(childId);
            queue.push(childId);
          }
        }
      }
    }
  }

  evaluateDispatchAdmission(taskDescriptor, triggerFamily, callerContext = {}) {
    if (!ALL_TRIGGER_FAMILIES.includes(triggerFamily)) {
      throw new Error(`Unknown trigger family: '${triggerFamily}'`);
    }

    // Check mutant bypass
    if (triggerFamily === 'FALLBACK' && this.allowFallbackBypass) {
      return { allowed: true, status: 'MUTANT_BYPASS' };
    }

    const { task_id, logical_work_id } = taskDescriptor;

    // 1. Direct uncertainty check on task_id
    if (this.uncertainTasks.has(task_id)) {
      throw new FatalExecutionUncertaintyBlocked(
        `[A01_FENCE_BLOCKED] Task '${task_id}' is in EXECUTION_UNCERTAIN state. Trigger family '${triggerFamily}' is strictly forbidden.`,
        { task_id, triggerFamily, record: this.uncertainTasks.get(task_id) }
      );
    }

    // 2. Logical work identity uncertainty check (prevents fallback/retry of identical work)
    if (logical_work_id && this.uncertainLogicalWork.has(logical_work_id)) {
      throw new FatalExecutionUncertaintyBlocked(
        `[A01_FENCE_BLOCKED] Logical work '${logical_work_id}' has an unresolved uncertain execution. Trigger family '${triggerFamily}' is strictly forbidden.`,
        { logical_work_id, task_id, triggerFamily }
      );
    }

    // 3. Dependent uncertainty check
    const currentStatus = this.taskStatuses.get(task_id);
    if (currentStatus === 'BLOCKED_DEPENDENT_UNCERTAIN') {
      throw new FatalExecutionUncertaintyBlocked(
        `[A01_FENCE_BLOCKED] Task '${task_id}' is BLOCKED_DEPENDENT_UNCERTAIN because an upstream dependency has unproven execution effects.`,
        { task_id, triggerFamily }
      );
    }

    return { allowed: true, status: 'ADMISSIBLE_FENCE_CLEAR', task_id, triggerFamily };
  }

  checkDispatchAllowed({ task_id, logical_work_id, dispatch_family = 'RETRY' }) {
    try {
      const family = ALL_TRIGGER_FAMILIES.includes(dispatch_family) ? dispatch_family : 'RETRY';
      this.evaluateDispatchAdmission({ task_id, logical_work_id }, family);
      return { allowed: true };
    } catch (err) {
      return { allowed: false, reason: err.message };
    }
  }

  reconcileProofOfEffect(taskId) {
    const record = this.uncertainTasks.get(taskId);
    this.uncertainTasks.delete(taskId);
    if (record && record.logical_work_id) {
      this.uncertainLogicalWork.delete(record.logical_work_id);
    }
    this.taskStatuses.set(taskId, 'CLOSED_SUCCESS');
    for (const [childId, parentSet] of this.dependencies.entries()) {
      if (parentSet.has(taskId)) {
        this.taskStatuses.set(childId, 'READY_FOR_DISPATCH');
      }
    }
  }

  reconcileProofOfNonEffect(taskId) {
    const record = this.uncertainTasks.get(taskId);
    this.uncertainTasks.delete(taskId);
    if (record && record.logical_work_id) {
      this.uncertainLogicalWork.delete(record.logical_work_id);
    }
    this.taskStatuses.set(taskId, 'ABORTED_NO_EFFECT');
  }

  resolveUncertainty(taskDescriptor, proofVerificationRecord) {
    const { task_id, logical_work_id } = taskDescriptor;

    if (!proofVerificationRecord || !proofVerificationRecord.verified) {
      throw new Error(
        `Cannot resolve uncertainty for task '${task_id}': Must provide verified proof record.`
      );
    }

    this.uncertainTasks.delete(task_id);
    if (logical_work_id) {
      this.uncertainLogicalWork.delete(logical_work_id);
    }
    this.taskStatuses.set(task_id, proofVerificationRecord.status || 'VERIFIED');

    // Re-evaluate downstream dependents
    this.recheckDownstreamDependents();

    return {
      resolved: true,
      task_id,
      resolved_at: new Date().toISOString()
    };
  }

  recheckDownstreamDependents() {
    for (const [childId, parentSet] of this.dependencies.entries()) {
      let anyParentUncertain = false;
      for (const parentId of parentSet) {
        if (this.uncertainTasks.has(parentId) || this.taskStatuses.get(parentId) === 'EXECUTION_UNCERTAIN') {
          anyParentUncertain = true;
          break;
        }
      }
      if (!anyParentUncertain && this.taskStatuses.get(childId) === 'BLOCKED_DEPENDENT_UNCERTAIN') {
        this.taskStatuses.set(childId, 'READY');
      }
    }
  }

  getAllTriggerFamilies() {
    return ALL_TRIGGER_FAMILIES;
  }
}

module.exports = {
  DispatcherUncertaintyFence,
  FatalExecutionUncertaintyBlocked,
  DependencyCycleError,
  ALL_TRIGGER_FAMILIES
};
