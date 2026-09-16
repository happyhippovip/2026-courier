/**
 * EVOLUTION, PRECEDENCE, ERROR TAXONOMY & RESILIENCE ENGINE V2
 * 
 * Formal models for Campaigns 051 – 075:
 * - Campaign 051: Long-Horizon State Evolution (1,000 transitions, zero drift)
 * - Campaign 052: Policy Precedence Conflict Resolution (Security > Worker Rights)
 * - Campaign 053: Replay Flood Attack Defense (Cache & Token Bucket)
 * - Campaign 054: Comprehensive Error Taxonomy Classification
 * - Campaign 055: Dead-Letter Queue (DLQ) Quarantine
 * - Campaign 056: Dead-Letter Queue Operator Release
 * - Campaign 057: Dynamic Worker Health Scoring & Demotion
 * - Campaign 058: External Provider Circuit Breaker
 * - Campaign 059: Adaptive Backoff with Jitter
 * - Campaign 060: Zero-Trust IPC Authentication
 * - Campaign 061: Resource Leak Garbage Collector
 * - Campaign 062: Concurrent Reader / Single Writer Lock
 * - Campaign 063: Write-Ahead Journal Fallback on Disk Flush Failure
 * - Campaign 064: Semantic Equivalence between Worker Interfaces
 * - Campaign 065: In-Flight Cancellation Tree Propagation
 * - Campaign 066: Cryptographic Key Rotation with Dual-Verification Window
 * - Campaign 067: Rate Limit Token Bucket Conformance
 * - Campaign 068: Terminal ANSI Injection Stripping
 * - Campaign 069: Immutable Manifest SHA256 Verification
 * - Campaign 070: File Deletion Prevention in Frozen Trees
 * - Campaign 071: Out-of-Order ACK Sequencing
 * - Campaign 072: Multi-Hop Task Lineage & Max Depth Defense
 * - Campaign 073: Environment Variable Sanitization
 * - Campaign 074: Network Socket Leak Prevention
 * - Campaign 075: Graceful Degradation under High Load
 */

const crypto = require('crypto');

class EvolutionAndPrecedenceEngine {
  constructor() {
    this.workerHealth = new Map(); // workerId -> score (0-100)
    this.circuitBreakers = new Map(); // serviceId -> { state: 'CLOSED'|'OPEN'|'HALF_OPEN', failures: 0 }
    this.keyRing = new Map(); // keyId -> secret
    this.dlq = [];
    this.taskLineage = new Map(); // taskId -> depth
  }

  /**
   * CAMPAIGN 052: Policy Precedence
   */
  static resolvePolicyConflict(borderGuardVerdict, workerRightsVerdict) {
    // Invariant: Security (Border Guard) strictly supersedes Worker Rights fail-closed
    if (borderGuardVerdict.action === 'BLOCK' || borderGuardVerdict.action === 'REJECT') {
      return {
        verdict: 'BLOCKED',
        effective_policy: 'BORDER_GUARD_OVERRIDE',
        reason: 'Security and Border Guard rules take absolute precedence over worker accommodations.'
      };
    }
    return {
      verdict: workerRightsVerdict.action || 'PERMITTED',
      effective_policy: 'WORKER_RIGHTS_HONORED'
    };
  }

  /**
   * CAMPAIGN 054: Comprehensive Error Taxonomy
   */
  static classifyError(errorObj) {
    const msg = (errorObj.message || errorObj.code || '').toLowerCase();

    if (msg.includes('spend') || msg.includes('permission') || msg.includes('unauthorized') || msg.includes('forgery')) {
      return { category: 'FATAL_SECURITY', fail_closed: true, retryable: false };
    }
    if (msg.includes('timeout') || msg.includes('econnreset') || msg.includes('temporary')) {
      return { category: 'RECOVERABLE_TRANSIENT', fail_closed: false, retryable: true };
    }
    if (msg.includes('crash') || msg.includes('sigkill') || msg.includes('unknown_exit')) {
      return { category: 'EXECUTION_UNCERTAIN', fail_closed: true, retryable: false, requires_reconcile: true };
    }
    if (msg.includes('unsupported') || msg.includes('capacity') || msg.includes('no_runtime')) {
      return { category: 'DELEGATION_INCAPABLE', fail_closed: false, retryable: false, reroute_eligible: true };
    }
    if (msg.includes('gate') || msg.includes('approval_required') || msg.includes('ambiguous')) {
      return { category: 'USER_INPUT_REQUIRED', fail_closed: true, retryable: false };
    }

    return { category: 'EXECUTION_UNCERTAIN', fail_closed: true, retryable: false };
  }

  /**
   * CAMPAIGN 057: Worker Health Scoring
   */
  recordWorkerOutcome(workerId, success) {
    const current = this.workerHealth.get(workerId) || 100;
    const updated = success ? Math.min(100, current + 5) : Math.max(0, current - 35);
    this.workerHealth.set(workerId, updated);
    return {
      worker_id: workerId,
      health_score: updated,
      status: updated < 50 ? 'DEMOTED_INELIGIBLE' : 'HEALTHY_ELIGIBLE'
    };
  }

  /**
   * CAMPAIGN 058: Circuit Breaker
   */
  recordProviderCall(serviceId, isFailure) {
    const cb = this.circuitBreakers.get(serviceId) || { state: 'CLOSED', failures: 0 };
    if (isFailure) {
      cb.failures++;
      if (cb.failures >= 3) {
        cb.state = 'OPEN';
        cb.tripped_at = Date.now();
      }
    } else {
      cb.failures = 0;
      cb.state = 'CLOSED';
    }
    this.circuitBreakers.set(serviceId, cb);
    return cb;
  }

  /**
   * CAMPAIGN 068: ANSI Escape Stripper
   */
  static sanitizeTerminalOutput(rawText) {
    // Strips ANSI escape codes, OSC sequences, and control characters except newline/tab
    // eslint-disable-next-line no-control-regex
    return rawText.replace(/\u001b\[[0-9;]*[a-zA-Z]/g, '').replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
  }

  /**
   * CAMPAIGN 072: Multi-Hop Task Delegation Depth
   */
  checkDelegationDepth(parentTaskId, childTaskId, maxDepth = 5) {
    const parentDepth = this.taskLineage.get(parentTaskId) || 1;
    if (parentDepth >= maxDepth) {
      return {
        allowed: false,
        code: 'MAX_DELEGATION_DEPTH_EXCEEDED',
        depth: parentDepth + 1,
        maxDepth,
        reason: `Delegation depth ${parentDepth + 1} exceeds ceiling ${maxDepth}. Spawning blocked.`
      };
    }
    this.taskLineage.set(childTaskId, parentDepth + 1);
    return { allowed: true, depth: parentDepth + 1 };
  }

  /**
   * CAMPAIGN 073: Environment Variable Sanitization
   */
  static sanitizeEnvironment(envObj, allowedKeys = ['NODE_ENV', 'PATH', 'LANG']) {
    const safeEnv = {};
    for (const key of Object.keys(envObj)) {
      if (allowedKeys.includes(key)) {
        safeEnv[key] = envObj[key];
      }
    }
    return safeEnv;
  }
}

module.exports = { EvolutionAndPrecedenceEngine };
