/**
 * INDEPENDENT ORACLE SUITE
 * 
 * Independent ground-truth models for differential testing:
 * - Oracle 1: State Transitions (Explicit transition table)
 * - Oracle 2: Logical Identity (Pure functional canonicalizer)
 * - Oracle 3: Human Gate Policy (Declarative rule engine)
 * - Oracle 4: Result Customs (Decision table)
 * - Oracle 5: Money Factory Revenue Truth (Ledger accounting math)
 */

const crypto = require('crypto');

class IndependentOracleSuite {
  /**
   * Oracle 1: State Transition Oracle
   * Pure declarative lookup table — zero algorithmic code shared with implementation.
   */
  static isTransitionLegal(fromState, toState) {
    const legalTransitions = {
      'CREATED': ['PLANNED', 'STAMPED', 'CANCELLED'],
      'PLANNED': ['STAMPED', 'CANCELLED'],
      'STAMPED': ['DISPATCHED', 'HOLD', 'CANCELLED'],
      'DISPATCHED': ['IN_FLIGHT', 'EXECUTION_UNCERTAIN', 'CANCELLED'],
      'IN_FLIGHT': ['RESULT_RECEIVED', 'EXECUTION_UNCERTAIN', 'CANCELLED'],
      'RESULT_RECEIVED': ['PENDING_VERIFY', 'EXECUTION_UNCERTAIN'],
      'PENDING_VERIFY': ['VERIFIED', 'FAILED', 'EXECUTION_UNCERTAIN'],
      'VERIFIED': ['COMPLETED', 'SUPERSEDED'],
      'FAILED': ['HOLD_FOR_TRIAGE', 'RE_ROUTING'],
      'EXECUTION_UNCERTAIN': ['RECONCILING', 'HELD_RECONCILIATION'],
      'RECONCILING': ['VERIFIED', 'FAILED', 'CANCELLED'],
      'HOLD': ['DISPATCHED', 'CANCELLED'],
      'COMPLETED': ['SUPERSEDED'],
      'CANCELLED': [],
      'SUPERSEDED': [],
      'BLOCKED': ['DISPATCHED', 'CANCELLED']
    };

    const allowed = legalTransitions[fromState] || [];
    return allowed.includes(toState);
  }

  /**
   * Oracle 2: Canonical Identity Oracle
   * Pure functional implementation using strictly sorted JSON key canonicalization.
   */
  static canonicalWorkIdentity(taskObject) {
    // Strictly isolate non-routing fields
    const essential = {
      criteria: taskObject.criteria || taskObject.acceptance_criteria || [],
      goal_id: taskObject.goal_id,
      instruction: taskObject.instruction || '',
      scope: (taskObject.scope || []).slice().sort()
    };
    const sortedKeys = Object.keys(essential).sort();
    const normalizedJson = JSON.stringify(essential, sortedKeys);
    return crypto.createHash('sha256').update(normalizedJson, 'utf8').digest('hex');
  }

  /**
   * Oracle 3: Human Gate Policy Oracle
   * Independent rule engine.
   */
  static evaluateHumanGate(operation, context) {
    const strictlyHumanOperations = [
      'LIVE_SPEND', 'REAL_TRADE', 'KEY_DESTRUCTION',
      'GIT_PUSH', 'PRODUCTION_DEPLOY', 'PUBLIC_OUTREACH'
    ];

    if (strictlyHumanOperations.includes(operation)) {
      return {
        requires_human: true,
        reason: `Operation ${operation} is intrinsically high-risk and requires human approval.`
      };
    }
    return {
      requires_human: false,
      reason: `Operation ${operation} is within autonomous sandbox authority.`
    };
  }

  /**
   * Oracle 4: Money Factory Revenue Truth Oracle
   */
  static evaluateRevenueTruth(event) {
    // Invariant: REAL_REVENUE_EUR is strictly 0 unless settlement signature is present and verified
    const isSettlement = event.type === 'BANK_SETTLEMENT' && event.verified === true;
    const realRevenueEur = isSettlement ? event.net_settled_eur : 0.00;
    const simulatedPnlEur = event.type === 'SIMULATED_ORDER' ? event.simulated_pnl_eur : 0.00;

    return {
      real_revenue_eur: realRevenueEur,
      simulated_pnl_eur: simulatedPnlEur,
      claim_valid: isSettlement || (!event.claimed_real_revenue || event.claimed_real_revenue === 0)
    };
  }
}

module.exports = { IndependentOracleSuite };
