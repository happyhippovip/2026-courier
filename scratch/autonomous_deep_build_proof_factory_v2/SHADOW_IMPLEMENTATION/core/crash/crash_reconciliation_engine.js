'use strict';

/**
 * SHADOW IMPLEMENTATION: CRASH RECONCILIATION ENGINE
 * Component: shadow/core/supervisor/crash_reconciliation_engine.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

const CRASH_LOCATIONS = Object.freeze({
  LOC_01_BEFORE_DISPATCH_PERSISTED: 'BEFORE_DISPATCH_PERSISTED',
  LOC_02_AFTER_DISPATCH_PERSISTED: 'AFTER_DISPATCH_PERSISTED',
  LOC_03_BEFORE_WORKER_STARTS: 'BEFORE_WORKER_STARTS',
  LOC_04_AFTER_WORKER_STARTS: 'AFTER_WORKER_STARTS',
  LOC_05_DURING_MUTATION: 'DURING_MUTATION',
  LOC_06_AFTER_RESULT_PRODUCED: 'AFTER_RESULT_PRODUCED',
  LOC_07_BEFORE_RESULT_PERSISTED: 'BEFORE_RESULT_PERSISTED',
  LOC_08_AFTER_RESULT_PERSISTED: 'AFTER_RESULT_PERSISTED',
  LOC_09_BEFORE_VERIFICATION: 'BEFORE_VERIFICATION',
  LOC_10_DURING_VERIFICATION: 'DURING_VERIFICATION',
  LOC_11_AFTER_VERIFICATION: 'AFTER_VERIFICATION',
  LOC_12_BEFORE_CLOSE: 'BEFORE_CLOSE'
});

class CrashReconciliationEngine {
  constructor(processOracle, options = {}) {
    this.processOracle = processOracle;
    this.resetUncertainToReady = options.resetUncertainToReady || false; // Dangerous mutant!
  }

  reconcileCrash(location, context = {}) {
    const { task, lease, osProcessInfo, deliverablesExistOnDisk, verificationResult } = context;

    switch (location) {
      case CRASH_LOCATIONS.LOC_01_BEFORE_DISPATCH_PERSISTED:
        return {
          action: 'DISCARD_UNRECORDED',
          targetState: 'PROPOSED',
          canDispatchFresh: true,
          reason: 'Dispatch was not recorded in durable journal; clean baseline'
        };

      case CRASH_LOCATIONS.LOC_02_AFTER_DISPATCH_PERSISTED:
        if (this.resetUncertainToReady) {
          return { action: 'MUTANT_UNSAFE_REDISPATCH', targetState: 'READY' };
        }
        return {
          action: 'FENCE_UNCERTAINTY',
          targetState: 'EXECUTION_UNCERTAIN',
          canDispatchFresh: false,
          reason: 'Dispatch persisted but worker outcome unknown; must fence'
        };

      case CRASH_LOCATIONS.LOC_03_BEFORE_WORKER_STARTS:
        return {
          action: 'RECLAIM_UNSTARTED_LEASE',
          targetState: 'APPROVED_FOR_DISPATCH',
          canDispatchFresh: true,
          reason: 'Worker never spawned; safe to reclaim lease and re-dispatch'
        };

      case CRASH_LOCATIONS.LOC_04_AFTER_WORKER_STARTS: {
        const identity = this.processOracle.evaluateProcessIdentity(lease, osProcessInfo);
        if (identity.verdict === 'MATCH') {
          return { action: 'REATTACH_SUPERVISOR', targetState: 'IN_FLIGHT', processLive: true };
        } else {
          return { action: 'FENCE_DISAPPEARED_WORKER', targetState: 'EXECUTION_UNCERTAIN', processLive: false };
        }
      }

      case CRASH_LOCATIONS.LOC_05_DURING_MUTATION:
        return {
          action: 'TRIGGER_ATOMIC_ROLLBACK',
          targetState: 'ROLLED_BACK',
          revertPartials: true,
          reason: 'Crashed during forward writes; must compensate LIFO snapshots'
        };

      case CRASH_LOCATIONS.LOC_06_AFTER_RESULT_PRODUCED:
      case CRASH_LOCATIONS.LOC_07_BEFORE_RESULT_PERSISTED:
        if (deliverablesExistOnDisk) {
          return {
            action: 'RECOVER_UNCOMMITTED_DELIVERABLES',
            targetState: 'RESULT_RECEIVED',
            reason: 'Deliverable files exist on disk with matching SHA-256'
          };
        } else {
          return {
            action: 'FENCE_MISSING_RESULT',
            targetState: 'EXECUTION_UNCERTAIN',
            reason: 'Result claimed but files missing on disk'
          };
        }

      case CRASH_LOCATIONS.LOC_08_AFTER_RESULT_PERSISTED:
      case CRASH_LOCATIONS.LOC_09_BEFORE_VERIFICATION:
        return {
          action: 'DISPATCH_VERIFIER',
          targetState: 'PENDING_VERIFY',
          reason: 'Result persisted; ready for independent verification'
        };

      case CRASH_LOCATIONS.LOC_10_DURING_VERIFICATION:
        return {
          action: 'RETRY_PURE_VERIFICATION',
          targetState: 'PENDING_VERIFY',
          reason: 'Verification is pure/read-only; safe to re-execute'
        };

      case CRASH_LOCATIONS.LOC_11_AFTER_VERIFICATION:
        return {
          action: 'ADVANCE_TO_CLOSE',
          targetState: verificationResult ? 'VERIFIED' : 'FAILED',
          reason: 'Verification completed prior to crash'
        };

      case CRASH_LOCATIONS.LOC_12_BEFORE_CLOSE:
        return {
          action: 'RELEASE_LEASES_AND_FINALIZE',
          targetState: 'CLOSED',
          reason: 'All deliverables verified; finalize lease releases'
        };

      default:
        throw new Error(`Unknown crash location: '${location}'`);
    }
  }
}

module.exports = {
  CRASH_LOCATIONS,
  CrashReconciliationEngine
};
