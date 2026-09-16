'use strict';

/**
 * SHADOW IMPLEMENTATION: TASK IDENTITY & FINGERPRINTING
 * Component: shadow/core/dispatch/task_identity.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

const crypto = require('crypto');

class IdentityConflationError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'IdentityConflationError';
    this.details = details;
  }
}

class TaskIdentityManager {
  constructor(options = {}) {
    this.acceptStaleVersionResult = options.acceptStaleVersionResult || false; // Mutant!
  }

  static computeInstructionFingerprint(instruction) {
    const normalized = (instruction || '').trim().replace(/\s+/g, ' ');
    return crypto.createHash('sha256').update(normalized).digest('hex').substring(0, 16);
  }

  static computeScopeFingerprint(targetPaths) {
    const sorted = [...(targetPaths || [])].map(p => p.replace(/\\/g, '/').toLowerCase()).sort();
    return crypto.createHash('sha256').update(JSON.stringify(sorted)).digest('hex').substring(0, 16);
  }

  static computeResultFingerprint(deliverables) {
    const sorted = Object.keys(deliverables || {}).sort().map(k => `${k}:${deliverables[k]}`);
    return crypto.createHash('sha256').update(sorted.join('|')).digest('hex').substring(0, 16);
  }

  createTaskDescriptor({
    task_id,
    task_version = 1,
    logical_work_id = null,
    goal_id,
    instruction,
    target_paths = []
  }) {
    if (!task_id) throw new Error('task_id is required');
    if (!goal_id) throw new Error('goal_id is required');

    const iFp = TaskIdentityManager.computeInstructionFingerprint(instruction);
    const sFp = TaskIdentityManager.computeScopeFingerprint(target_paths);
    const effLogicalWorkId = logical_work_id || `work_${iFp}_${sFp}`;

    return {
      task_id,
      task_version,
      logical_work_id: effLogicalWorkId,
      goal_id,
      instruction,
      instruction_fingerprint: iFp,
      scope_fingerprint: sFp,
      target_paths,
      created_at: new Date().toISOString()
    };
  }

  validateResultSubmission(taskDescriptor, resultPayload) {
    const { target_task_id, target_task_version, deliverables } = resultPayload;

    if (target_task_id !== taskDescriptor.task_id) {
      throw new IdentityConflationError(
        `Task ID mismatch: result targeted '${target_task_id}' but active task is '${taskDescriptor.task_id}'`,
        { target_task_id, actual_task_id: taskDescriptor.task_id }
      );
    }

    if (!this.acceptStaleVersionResult) {
      if (target_task_version !== taskDescriptor.task_version) {
        throw new IdentityConflationError(
          `Stale version result rejected: result targeted version ${target_task_version}, but task is at version ${taskDescriptor.task_version}`,
          { target_version: target_task_version, active_version: taskDescriptor.task_version }
        );
      }
    }

    const rFp = TaskIdentityManager.computeResultFingerprint(deliverables);
    return {
      valid: true,
      result_fingerprint: rFp,
      task_id: taskDescriptor.task_id,
      task_version: taskDescriptor.task_version,
      logical_work_id: taskDescriptor.logical_work_id
    };
  }
}

module.exports = {
  TaskIdentityManager,
  IdentityConflationError
};
