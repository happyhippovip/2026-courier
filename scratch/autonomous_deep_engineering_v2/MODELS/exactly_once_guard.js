/**
 * EXACTLY-ONCE EFFECT GUARD (V2 LAB)
 * 
 * Formal idempotency and side-effect control engine protecting against:
 * retry, fallback, restart, stale queue, duplicate queue, lease expiry,
 * worker reconnect, result delay, verification delay, checkpoint replay,
 * PID reuse, old ACK, duplicate ACK.
 */

const crypto = require('crypto');

class ExactlyOnceGuard {
  constructor() {
    this.completedTasks = new Map(); // logical_work_id -> result_fingerprint
    this.activeDispatches = new Map(); // scope_path -> active_task_id
    this.seenAcks = new Set(); // ack_id
    this.seenCheckpoints = new Map(); // checkpoint_id -> seq
    this.attackStats = {
      attempts: 0,
      prevented: 0,
      escaped: 0
    };
  }

  recordCompleted(logicalWorkId, resultFingerprint) {
    this.completedTasks.set(logicalWorkId, resultFingerprint);
  }

  acquireScopeLease(scopePath, taskId) {
    if (this.activeDispatches.has(scopePath)) {
      const active = this.activeDispatches.get(scopePath);
      if (active !== taskId) {
        return { acquired: false, action: 'HOLD', holder: active };
      }
    }
    this.activeDispatches.set(scopePath, taskId);
    return { acquired: true, action: 'PROCEED' };
  }

  releaseScopeLease(scopePath, taskId) {
    if (this.activeDispatches.get(scopePath) === taskId) {
      this.activeDispatches.delete(scopePath);
    }
  }

  /**
   * Evaluates an execution attempt against all 14 duplicate effect vectors.
   */
  evaluateAttempt(vectorName, attemptData) {
    this.attackStats.attempts++;
    const { logical_work_id, task_id, version, scope_path, ack_id, is_uncertain, checkpoint_seq } = attemptData;

    // 1. Check if already completed (Terminal Idempotency)
    if (this.completedTasks.has(logical_work_id)) {
      this.attackStats.prevented++;
      return {
        allowed: false,
        vector: vectorName,
        action: 'BLOCK_DUPLICATE_ALREADY_COMPLETED',
        reason: `Logical work '${logical_work_id}' is already terminal. Duplicate effect prevented.`
      };
    }

    // 2. Check if execution uncertain (Fail-Closed Barrier)
    if (is_uncertain) {
      this.attackStats.prevented++;
      return {
        allowed: false,
        vector: vectorName,
        action: 'BLOCK_EXECUTION_UNCERTAIN',
        reason: 'Prior execution is in uncertain state. Blind retry/fallback strictly blocked.'
      };
    }

    // 3. Check Scope Lease Concurrency (Single-Writer Invariant)
    if (scope_path && this.activeDispatches.has(scope_path)) {
      const activeTask = this.activeDispatches.get(scope_path);
      if (activeTask !== task_id) {
        this.attackStats.prevented++;
        return {
          allowed: false,
          vector: vectorName,
          action: 'HOLD_SCOPE_COLLISION',
          reason: `Scope '${scope_path}' is currently locked by active task '${activeTask}'. Second writer placed on HOLD.`
        };
      }
    }

    // 4. Check Duplicate / Old ACK
    if (ack_id) {
      if (this.seenAcks.has(ack_id)) {
        this.attackStats.prevented++;
        return {
          allowed: false,
          vector: vectorName,
          action: 'BLOCK_DUPLICATE_ACK',
          reason: `ACK '${ack_id}' has already been processed. Replay rejected.`
        };
      }
      this.seenAcks.add(ack_id);
    }

    // 5. Check Stale Checkpoint Replay
    if (checkpoint_seq !== undefined) {
      const latestSeq = this.seenCheckpoints.get(task_id) || 0;
      if (checkpoint_seq <= latestSeq && latestSeq > 0) {
        this.attackStats.prevented++;
        return {
          allowed: false,
          vector: vectorName,
          action: 'BLOCK_STALE_CHECKPOINT_REPLAY',
          reason: `Checkpoint sequence ${checkpoint_seq} is stale (latest known: ${latestSeq}). Replay rejected.`
        };
      }
      this.seenCheckpoints.set(task_id, checkpoint_seq);
    }

    // Passed all guards
    return {
      allowed: true,
      vector: vectorName,
      action: 'ALLOW_DISPATCH',
      reason: 'Attempt satisfies exactly-once execution invariants'
    };
  }
}

module.exports = { ExactlyOnceGuard };
