'use strict';

const crypto = require('crypto');

/**
 * RollbackEngine
 * Executes compensating transactions in strict LIFO (Last-In-First-Out) order
 * when a migration or operational transaction suffers an unrecoverable failure.
 */
class RollbackEngine {
  constructor() {
    this.actionStack = [];
    this.executedRollbacks = [];
  }

  recordAction(action) {
    if (!action || !action.action_id || !action.type || typeof action.compensate !== 'function') {
      throw new Error('Action must have action_id, type, and compensate function');
    }
    this.actionStack.push(action);
  }

  computeStateHash(stateObj) {
    return crypto.createHash('sha256').update(JSON.stringify(stateObj)).digest('hex');
  }

  executeRollback(expectedBaselineHash = null, getCurrentStateFn = null) {
    const rolledBack = [];

    // LIFO execution: pop from end
    while (this.actionStack.length > 0) {
      const action = this.actionStack.pop();
      try {
        const result = action.compensate();
        rolledBack.push({ action_id: action.action_id, type: action.type, result, status: 'REVERTED' });
        this.executedRollbacks.push(action.action_id);
      } catch (err) {
        throw new Error(`Rollback compensation failed for action ${action.action_id}: ${err.message}`);
      }
    }

    // Verify post-rollback integrity
    let integrityVerified = true;
    let actualHash = null;
    if (expectedBaselineHash && typeof getCurrentStateFn === 'function') {
      actualHash = this.computeStateHash(getCurrentStateFn());
      if (actualHash !== expectedBaselineHash) {
        integrityVerified = false;
        throw new Error(`ROLLBACK_INTEGRITY_VIOLATION: Expected hash ${expectedBaselineHash}, got ${actualHash}`);
      }
    }

    return {
      success: true,
      rolled_back_count: rolledBack.length,
      actions: rolledBack,
      integrity_verified: integrityVerified,
      state_hash: actualHash
    };
  }
}

module.exports = { RollbackEngine };
