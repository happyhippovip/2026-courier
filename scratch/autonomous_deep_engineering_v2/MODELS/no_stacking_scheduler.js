/**
 * NO-STACKING SCHEDULER & CONCURRENCY ENGINE (V2 LAB)
 * 
 * Formal concurrency engine enforcing:
 * Conflicting second writer is placed on HOLD, never dispatched concurrently.
 * Distinguishes read vs write leases, detects disguised writers, and isolates follow-ups.
 */

class NoStackingScheduler {
  constructor() {
    this.activeWriterLeases = new Map(); // scope -> taskId
    this.activeReadLeases = new Map();   // scope -> Set(taskIds)
    this.followUpInbox = [];             // out-of-band thoughts
    this.stats = {
      arrivals: 0,
      dispatched: 0,
      held_on_collision: 0,
      stacking_escaped: 0
    };
  }

  static detectImplicitWrites(command) {
    const writePatterns = [
      />/i,
      /\bwrite\b/i,
      /\bupdate\b/i,
      /\bmodify\b/i,
      /\bbuild\b/i,
      /\binstall\b/i,
      /\bclean\b/i,
      /\brm\b/i,
      /\bmkdir\b/i,
      /\bpatch\b/i
    ];
    return writePatterns.some(p => p.test(command || ''));
  }

  evaluateArrival(arrival) {
    this.stats.arrivals++;
    const { task_id, worker_id, scope_paths = [], is_writer = true, command, is_follow_up, priority } = arrival;

    // 1. Follow-up ideas arriving during execution are captured out-of-band
    if (is_follow_up) {
      this.followUpInbox.push({
        id: `FUP-${Date.now()}-${task_id}`,
        task_id,
        worker_id,
        priority: priority || 'NORMAL',
        status: 'CAPTURED_NON_DISRUPTIVE'
      });
      return {
        action: 'INBOX_CAPTURED',
        reason: 'Follow-up captured out-of-band without interrupting in-flight execution.'
      };
    }

    // 2. Detect Disguised Writers: claimed read-only but command writes
    let effectiveWriter = is_writer;
    if (!effectiveWriter && NoStackingScheduler.detectImplicitWrites(command)) {
      effectiveWriter = true; // Demote/reclassify to writer
    }

    // 3. Evaluate scope collisions
    for (const scope of scope_paths) {
      // If any active writer exists on scope -> HOLD
      if (this.activeWriterLeases.has(scope)) {
        const holder = this.activeWriterLeases.get(scope);
        if (holder !== task_id) {
          this.stats.held_on_collision++;
          return {
            action: 'HOLD',
            conflicting_scope: scope,
            active_holder: holder,
            reason: `Scope '${scope}' is locked by active writer '${holder}'. Concurrency conflict -> HOLD.`
          };
        }
      }

      // If this arrival is a writer and active readers exist -> HOLD
      if (effectiveWriter && this.activeReadLeases.has(scope) && this.activeReadLeases.get(scope).size > 0) {
        this.stats.held_on_collision++;
        return {
          action: 'HOLD',
          conflicting_scope: scope,
          active_readers: Array.from(this.activeReadLeases.get(scope)),
          reason: `Scope '${scope}' has active readers. Writer must HOLD until readers finish.`
        };
      }
    }

    // 4. Safe to dispatch: grant leases
    if (effectiveWriter) {
      for (const scope of scope_paths) {
        this.activeWriterLeases.set(scope, task_id);
      }
    } else {
      for (const scope of scope_paths) {
        if (!this.activeReadLeases.has(scope)) this.activeReadLeases.set(scope, new Set());
        this.activeReadLeases.get(scope).add(task_id);
      }
    }

    this.stats.dispatched++;
    return {
      action: 'DISPATCH',
      effective_writer: effectiveWriter,
      scopes_granted: scope_paths,
      reason: 'No conflicting leases. Dispatched safely.'
    };
  }

  releaseLeases(taskId) {
    for (const [scope, holder] of this.activeWriterLeases.entries()) {
      if (holder === taskId) this.activeWriterLeases.delete(scope);
    }
    for (const [scope, readers] of this.activeReadLeases.entries()) {
      readers.delete(taskId);
      if (readers.size === 0) this.activeReadLeases.delete(scope);
    }
  }
}

module.exports = { NoStackingScheduler };
