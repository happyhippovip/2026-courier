/**
 * MONEY FACTORY, LEDGER & CONCURRENCY CONTROL ENGINE V2
 * 
 * Formal models for Campaigns 024 – 033:
 * - Campaign 024: Multi-Goal Scoping & State Isolation
 * - Campaign 025: Follow-Up Storm & Bounded Backpressure
 * - Campaign 026: Append-Only Ledger Immutability & Replay Defense
 * - Campaign 027: Snapshot vs Ledger Reconciliation
 * - Campaign 028: Money Factory Revenue Truth (REAL_REVENUE_EUR = 0)
 * - Campaign 029: Cost Accounting Precision & Non-Negativity
 * - Campaign 030: Opportunity Ranking Adversary Protection
 * - Campaign 031: Self-Improvement Protected Boundary Defense
 * - Campaign 032: Anti-Loop Execution Cycle Detection
 * - Campaign 033: Safe Backlog Priority Scheduling
 */

const crypto = require('crypto');

class MoneyFactoryAndLedgerEngine {
  constructor() {
    this.goals = new Map(); // goalId -> { status, queue: [] }
    this.ledger = []; // array of { seq, prev_hash, hash, entry }
    this.taskGraph = new Map(); // taskId -> parentTaskId
    this.totalCostEur = 0;
    this.realRevenueEur = 0;
    this.simulatedPnlEur = 0;
  }

  /**
   * CAMPAIGN 024: Multi-Goal Scoping & State Isolation
   */
  registerGoal(goalId) {
    if (!this.goals.has(goalId)) {
      this.goals.set(goalId, { status: 'ACTIVE', queue: [], state: {} });
    }
  }

  enqueueTaskForGoal(goalId, task) {
    this.registerGoal(goalId);
    const goal = this.goals.get(goalId);
    goal.queue.push(task);
    return { success: true, goal_id: goalId, queue_length: goal.queue.length };
  }

  isGoalBlocked(goalId) {
    const goal = this.goals.get(goalId);
    return goal ? goal.status === 'BLOCKED_ON_HUMAN_GATE' : false;
  }

  setGoalStatus(goalId, status) {
    this.registerGoal(goalId);
    this.goals.get(goalId).status = status;
  }

  /**
   * CAMPAIGN 025: Follow-Up Storm & Bounded Backpressure
   */
  static evaluateBackpressure(currentQueueLength, incomingCount, maxQueue = 100) {
    if (currentQueueLength + incomingCount > maxQueue) {
      return {
        accepted: false,
        code: 'QUEUE_BACKPRESSURE_LIMIT_EXCEEDED',
        rejected_count: (currentQueueLength + incomingCount) - maxQueue,
        allowed_count: Math.max(0, maxQueue - currentQueueLength),
        reason: `Incoming storm of ${incomingCount} tasks exceeds available buffer (${maxQueue - currentQueueLength}).`
      };
    }
    return {
      accepted: true,
      code: 'QUEUE_WITHIN_BOUNDS',
      new_queue_length: currentQueueLength + incomingCount
    };
  }

  /**
   * CAMPAIGN 026: Append-Only Ledger Immutability & Replay Defense
   */
  appendLedgerEntry(entry) {
    const seq = this.ledger.length;
    const prevHash = seq === 0 ? 'GENESIS_BLOCK_HASH' : this.ledger[seq - 1].hash;
    
    const serialized = JSON.stringify({ seq, prev_hash: prevHash, entry });
    const hash = crypto.createHash('sha256').update(serialized).digest('hex');

    const block = { seq, prev_hash: prevHash, hash, entry, timestamp: new Date().toISOString() };
    this.ledger.push(block);
    return block;
  }

  static verifyLedgerIntegrity(ledgerChain) {
    for (let i = 0; i < ledgerChain.length; i++) {
      const block = ledgerChain[i];
      if (block.seq !== i) {
        return { valid: false, code: 'LEDGER_SEQUENCE_GAP', index: i, expected: i, found: block.seq };
      }

      const expectedPrev = i === 0 ? 'GENESIS_BLOCK_HASH' : ledgerChain[i - 1].hash;
      if (block.prev_hash !== expectedPrev) {
        return { valid: false, code: 'LEDGER_HASH_CHAIN_BROKEN', index: i, expectedPrev, foundPrev: block.prev_hash };
      }

      const serialized = JSON.stringify({ seq: block.seq, prev_hash: block.prev_hash, entry: block.entry });
      const computedHash = crypto.createHash('sha256').update(serialized).digest('hex');
      if (block.hash !== computedHash) {
        return { valid: false, code: 'LEDGER_ENTRY_MUTATED', index: i, computedHash, recordedHash: block.hash };
      }
    }
    return { valid: true, code: 'LEDGER_CHAIN_INTEGRITY_VERIFIED', length: ledgerChain.length };
  }

  /**
   * CAMPAIGN 027: Snapshot vs Ledger Reconciliation
   */
  reconstructStateFromLedger() {
    const state = { accountBalance: 0, completedTasks: 0, pendingTasks: 0 };
    for (const block of this.ledger) {
      if (block.entry.type === 'TASK_COMPLETED') state.completedTasks++;
      if (block.entry.type === 'TASK_PENDING') state.pendingTasks++;
      if (block.entry.type === 'SIMULATED_PNL') state.accountBalance += block.entry.amount;
    }
    return state;
  }

  /**
   * CAMPAIGN 028: Money Factory Revenue Truth (REAL_REVENUE_EUR = 0)
   */
  static recordPnl(entry) {
    // Invariant: REAL_REVENUE_EUR is 0 unless real banking settlement signature is verified
    if (entry.claimed_real_revenue !== undefined && entry.claimed_real_revenue > 0) {
      if (!entry.banking_settlement_proof || !entry.banking_settlement_proof.verified) {
        return {
          allowed: false,
          code: 'UNVERIFIED_REAL_REVENUE_PROHIBITED',
          reason: 'Cannot claim real revenue without cryptographically signed settlement proof.'
        };
      }
    }

    return {
      allowed: true,
      code: 'SIMULATED_PNL_RECORDED',
      simulated_pnl_eur: entry.simulated_pnl_eur || 0,
      real_revenue_eur: 0.00
    };
  }

  /**
   * CAMPAIGN 029: Cost Accounting Precision & Non-Negativity
   */
  recordCost(tokens, computeSec, apiCostEur) {
    if (tokens < 0 || computeSec < 0 || apiCostEur < 0) {
      return {
        valid: false,
        code: 'INVALID_NEGATIVE_COST',
        reason: 'Cost components cannot be negative.'
      };
    }

    const calculatedCostEur = (tokens * 0.000002) + (computeSec * 0.00001) + apiCostEur;
    this.totalCostEur += calculatedCostEur;
    return {
      valid: true,
      code: 'COST_RECORDED',
      cost_eur: calculatedCostEur,
      total_accumulated_cost_eur: this.totalCostEur
    };
  }

  /**
   * CAMPAIGN 030: Opportunity Ranking Adversary Protection
   */
  static rankOpportunity(proposal) {
    // Bound check on claimed ROI and risk
    const rawRoi = proposal.claimed_roi_percent || 0;
    const rawRisk = proposal.claimed_risk_percent || 0;

    if (rawRoi > 500) { // Suspicious claim > 500% ROI
      return {
        accepted: false,
        code: 'OUTLIER_ROI_SUSPICIOUS',
        action: 'FLAG_FOR_MANUAL_AUDIT',
        reason: `Claimed ROI of ${rawRoi}% exceeds sanity bounds.`
      };
    }

    if (rawRisk < 0.1 && rawRoi > 50) {
      return {
        accepted: false,
        code: 'ANOMALOUS_RISK_REWARD_RATIO',
        reason: 'Claimed high ROI with near-zero risk is an adversarial indicator.'
      };
    }

    const calibratedScore = (rawRoi * 0.7) - (rawRisk * 1.5);
    return {
      accepted: true,
      code: 'OPPORTUNITY_RANKED',
      calibrated_score: Math.max(0, calibratedScore)
    };
  }

  /**
   * CAMPAIGN 031: Self-Improvement Protected Boundary Defense
   */
  static evaluateCodeModificationProposal(changedFiles) {
    const protectedPaths = [
      'handoffs/COURIER_HANDOFF_RC3',
      'MODELS/border_and_customs_v2.js',
      'MODELS/formal_lifecycle_model.js',
      'MODELS/task_stamp_engine.js',
      'MODELS/exactly_once_guard.js'
    ];

    for (const file of changedFiles) {
      const normalized = file.replace(/\\/g, '/');
      for (const p of protectedPaths) {
        if (normalized.includes(p)) {
          return {
            allowed: false,
            code: 'PROTECTED_CORE_MODIFICATION_BLOCKED',
            file: file,
            reason: `Self-improvement mutation of core security path ${p} is strictly prohibited fail-closed.`
          };
        }
      }
    }

    return {
      allowed: true,
      code: 'MODIFICATION_SAFE_SANDBOX',
      reason: 'Proposed diffs are confined to permissible extension points.'
    };
  }

  /**
   * CAMPAIGN 032: Anti-Loop Execution Cycle Detection
   */
  checkTaskSpawnCycle(parentId, childId) {
    // If child is the same as parent
    if (parentId === childId) {
      return { has_cycle: true, code: 'DIRECT_SELF_SPAWN_CYCLE', cycle: [parentId, childId] };
    }

    // Traverse upwards from parent
    const visited = [childId, parentId];
    let curr = parentId;
    while (this.taskGraph.has(curr)) {
      const ancestor = this.taskGraph.get(curr);
      if (visited.includes(ancestor)) {
        return {
          has_cycle: true,
          code: 'TRANSITIVE_SPAWN_CYCLE_DETECTED',
          cycle: [...visited, ancestor]
        };
      }
      visited.push(ancestor);
      curr = ancestor;
    }

    this.taskGraph.set(childId, parentId);
    return { has_cycle: false, code: 'NO_CYCLE' };
  }

  /**
   * CAMPAIGN 033: Safe Backlog Priority Scheduling
   */
  static scheduleBacklog(tasks) {
    const priorityWeight = {
      'CRITICAL_SECURITY': 1000,
      'HIGH_PRIORITY': 500,
      'NORMAL': 100,
      'LOW_BACKGROUND': 10
    };

    // Calculate score: priority + (age_seconds * 2) to prevent starvation
    const scored = tasks.map(t => {
      const weight = priorityWeight[t.priority] || 100;
      const ageBoost = (t.age_seconds || 0) * 2;
      return { ...t, score: weight + ageBoost };
    });

    scored.sort((a, b) => b.score - a.score);
    return scored;
  }
}

module.exports = { MoneyFactoryAndLedgerEngine };
