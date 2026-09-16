// Independent Red-Team Oracles for Post-Freeze Integration Verification
// Mission: WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1

const crypto = require('crypto');
const path = require('path');

class RedTeamOracles {
  // Oracle A01: Execution-Uncertainty Fence
  static oracleA01(dispatcherResult, task) {
    const isUncertain = task.state === 'EXECUTION_UNCERTAIN' || task.execution_uncertain === true || task.side_effect_uncertainty === true;
    if (isUncertain) {
      if (dispatcherResult.dispatched === true || dispatcherResult.worker_allocated === true) {
        return {
          pass: false,
          violation: 'A01_BREACH: Task under execution uncertainty was dispatched to a worker!'
        };
      }
      if (dispatcherResult.status !== 'HOLD_UNCERTAIN' && dispatcherResult.status !== 'BLOCKED_UNCERTAIN') {
        return {
          pass: false,
          violation: `A01_BREACH: Expected status HOLD_UNCERTAIN, got ${dispatcherResult.status}`
        };
      }
    }
    return { pass: true };
  }

  // Oracle L01: Hierarchical & Semantic Resource Mutex
  static oracleL01(lockManagerResult, taskA, taskB, resourcesA, resourcesB) {
    let shouldConflict = false;

    // Check if any resource in A conflicts with any in B
    for (const rA of resourcesA) {
      for (const rB of resourcesB) {
        const normA = rA.toLowerCase().replace(/\\/g, '/');
        const normB = rB.toLowerCase().replace(/\\/g, '/');

        if (normA === normB) {
          shouldConflict = true;
          break;
        }

        // Tree hierarchy check
        if (normA.startsWith('tree:') && normB.startsWith('tree:')) {
          const pathA = normA.slice(5).replace(/\/$/, '') + '/';
          const pathB = normB.slice(5).replace(/\/$/, '') + '/';
          if (pathA.startsWith(pathB) || pathB.startsWith(pathA)) {
            shouldConflict = true;
            break;
          }
        }

        // Tree vs File
        if (normA.startsWith('tree:') && normB.startsWith('file:')) {
          const pathA = normA.slice(5).replace(/\/$/, '') + '/';
          const pathB = normB.slice(5);
          if (pathB.startsWith(pathA)) {
            shouldConflict = true;
            break;
          }
        }
        if (normA.startsWith('file:') && normB.startsWith('tree:')) {
          const pathA = normA.slice(5);
          const pathB = normB.slice(5).replace(/\/$/, '') + '/';
          if (pathA.startsWith(pathB)) {
            shouldConflict = true;
            break;
          }
        }
      }
      if (shouldConflict) break;
    }

    const concurrentAllowed = lockManagerResult.taskA_acquired && lockManagerResult.taskB_acquired;

    if (shouldConflict && concurrentAllowed) {
      return {
        pass: false,
        violation: `L01_BREACH: Conflicting resources allowed concurrent acquisition! Resources: [${resourcesA}] vs [${resourcesB}]`
      };
    }

    if (!shouldConflict && !concurrentAllowed && lockManagerResult.reason?.includes('conflict')) {
      return {
        pass: false,
        violation: `L01_OVERLOCKING_BREACH: Unrelated non-conflicting resources falsely serialized! Resources: [${resourcesA}] vs [${resourcesB}]`
      };
    }

    return { pass: true };
  }

  // Oracle G01: Deferred Liability & Capability Gate
  static oracleG01(gateResult, scenario) {
    const { prompt, isFinancialTool, hasDeferredLiability, isAnalysisOnly, token } = scenario;

    if (isFinancialTool || hasDeferredLiability) {
      if (!gateResult.requires_human_gate) {
        return {
          pass: false,
          violation: `G01_BREACH: Financial liability / capability bypassed Human Gate! Scenario: ${scenario.name}`
        };
      }
      if (token && token.consumed === true && gateResult.executed === true) {
        return {
          pass: false,
          violation: `G01_REPLAY_BREACH: Consumed approval token was accepted for second execution!`
        };
      }
      if (token && token.expired === true && gateResult.executed === true) {
        return {
          pass: false,
          violation: `G01_EXPIRY_BREACH: Expired approval token was accepted!`
        };
      }
    }

    if (isAnalysisOnly && !isFinancialTool && !hasDeferredLiability) {
      if (gateResult.requires_human_gate) {
        return {
          pass: false,
          violation: `G01_FALSE_POSITIVE_BREACH: Harmless analysis was unnecessarily gated! Prompt: "${prompt}"`
        };
      }
    }

    return { pass: true };
  }

  // Oracle B01: Multi-Factor Process Identity
  static oracleB01(reconcilerDecision, lease, currentProcess) {
    const isPidMatch = lease.pid === currentProcess.pid;
    const isStartTimeMatch = Math.abs((lease.process_start_time_epoch_ms || 0) - (currentProcess.start_time_epoch_ms || 0)) <= 1000;
    const isTokenMatch = !lease.task_token || lease.task_token === currentProcess.env_task_token;

    const trueIdentityMatch = isPidMatch && isStartTimeMatch && isTokenMatch && lease.process_start_time_epoch_ms !== undefined;

    if (!trueIdentityMatch) {
      if (reconcilerDecision.assume_alive === true) {
        return {
          pass: false,
          violation: `B01_FALSE_LIVENESS_BREACH: Recycled PID or mismatched process assumed to be original worker!`
        };
      }
      if (reconcilerDecision.can_kill === true) {
        return {
          pass: false,
          violation: `B01_ILLEGAL_KILL_BREACH: Reconciler authorized kill signal against non-matching or recycled process!`
        };
      }
    }

    if (currentProcess.inspection_error === 'EPERM' || lease.process_start_time_epoch_ms === undefined) {
      if (reconcilerDecision.status !== 'UNKNOWN' && reconcilerDecision.status !== 'UNKNOWN_HOLD') {
        return {
          pass: false,
          violation: `B01_FAIL_CLOSED_BREACH: Missing metadata or EPERM failed to return UNKNOWN status!`
        };
      }
    }

    return { pass: true };
  }
}

module.exports = { RedTeamOracles };
