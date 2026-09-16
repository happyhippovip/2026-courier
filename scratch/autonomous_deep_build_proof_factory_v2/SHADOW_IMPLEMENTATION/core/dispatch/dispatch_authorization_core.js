'use strict';

/**
 * SHADOW IMPLEMENTATION: DISPATCH AUTHORIZATION CORE
 * Component: shadow/core/dispatch/dispatch_authorization_core.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

class DispatchAuthorizationCore {
  constructor(uncertaintyFence, options = {}) {
    this.fence = uncertaintyFence;
  }

  evaluateDispatch(request) {
    const {
      taskDescriptor,
      triggerFamily = 'RETRY',
      borderGuardVerdict = 'GREEN_CARD',
      hasRequiredLeases = true,
      requiresHumanGate = false,
      hasValidGateToken = false,
      governorAdmissible = true
    } = request;

    // 1. First priority: Check Execution Uncertainty Fence (A01)
    try {
      this.fence.evaluateDispatchAdmission(taskDescriptor, triggerFamily);
    } catch (fenceErr) {
      if (fenceErr.name === 'FatalExecutionUncertaintyBlocked') {
        return {
          verdict: 'EXECUTION_UNCERTAIN',
          reason: fenceErr.message,
          error: fenceErr
        };
      }
      throw fenceErr;
    }

    // 2. Second priority: Human Gate check
    if (requiresHumanGate) {
      if (!hasValidGateToken) {
        return {
          verdict: 'HUMAN_GATE',
          reason: 'Operation requires operator authorization token prior to dispatch.'
        };
      }
    }

    // 3. Third priority: Border Guard security verdict
    if (borderGuardVerdict !== 'GREEN_CARD') {
      return {
        verdict: 'BLOCK',
        reason: `Border guard denied dispatch with verdict: '${borderGuardVerdict}'`
      };
    }

    // 4. Fourth priority: Concurrency and Resource Leases
    if (!hasRequiredLeases) {
      return {
        verdict: 'HOLD',
        reason: 'Required mutex or resource lease is currently held by another worker.'
      };
    }

    // 5. Fifth priority: Host Resource Governor
    if (!governorAdmissible) {
      return {
        verdict: 'HOLD',
        reason: 'Host resource governor throttled admission due to memory/thermal backpressure.'
      };
    }

    // All gates pass
    return {
      verdict: 'ALLOW',
      status: 'AUTHORIZED_FOR_DISPATCH',
      task_id: taskDescriptor.task_id,
      task_version: taskDescriptor.task_version
    };
  }
}

module.exports = {
  DispatchAuthorizationCore
};
