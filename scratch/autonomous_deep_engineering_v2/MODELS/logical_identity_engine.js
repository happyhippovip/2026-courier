/**
 * LOGICAL IDENTITY & DISPATCH ROUTING ENGINE (V2 LAB)
 * 
 * Formal engine enforcing:
 * ROUTING MUST NOT SILENTLY CREATE NEW LOGICAL WORK.
 * 
 * Separates immutable logical identity from dynamic dispatch/attempt metadata.
 */

const crypto = require('crypto');

class LogicalIdentityEngine {
  /**
   * Computes the immutable canonical fingerprint of the logical task.
   * Based strictly on semantic work definition; zero route or worker dependencies.
   */
  static computeCanonicalTaskHash({
    goal_id,
    mission_id,
    task_id,
    version = 1,
    command,
    scope_paths = [],
    acceptance_criteria = []
  }) {
    if (!goal_id || !task_id || !command) {
      throw new Error('[IDENTITY_ERROR] goal_id, task_id, and command required');
    }

    const normalizedScopes = Array.from(new Set(scope_paths.map(s => s.replace(/\\/g, '/')))).sort();
    const normalizedCriteria = Array.from(new Set(acceptance_criteria.map(c => c.trim()))).sort();

    const semanticPayload = {
      goal_id,
      mission_id,
      task_id,
      version,
      command: command.trim(),
      scope_paths: normalizedScopes,
      acceptance_criteria: normalizedCriteria
    };

    return crypto.createHash('sha256').update(JSON.stringify(semanticPayload)).digest('hex');
  }

  /**
   * Wraps the logical task into a dispatch attempt envelope.
   * Physical worker, route, and attempt IDs live HERE, decoupled from task hash.
   */
  static createDispatchEnvelope(task, {
    worker_id,
    route_type = 'DIRECT',
    attempt_number = 1,
    previous_attempt_id = null
  }) {
    const canonicalHash = LogicalIdentityEngine.computeCanonicalTaskHash(task);
    const attemptId = `ATT-${task.task_id}-V${task.version}-TRY${attempt_number}-${crypto.randomBytes(2).toString('hex')}`;

    return {
      dispatch_attempt_id: attemptId,
      canonical_task_hash: canonicalHash,
      task_id: task.task_id,
      task_version: task.version,
      goal_id: task.goal_id,
      mission_id: task.mission_id,
      assigned_worker_id: worker_id,
      route_type,
      attempt_number,
      previous_attempt_id,
      dispatched_at: new Date().toISOString()
    };
  }

  /**
   * Flawed reference model (demonstrates the hash-mismatch / identity drift bug)
   * Incorrectly incorporates worker_id and attempt timestamp into the task identity hash.
   */
  static computeFlawedTaskHash(task, worker_id, timestamp) {
    const payload = {
      ...task,
      worker_id,
      timestamp
    };
    return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  }
}

module.exports = { LogicalIdentityEngine };
