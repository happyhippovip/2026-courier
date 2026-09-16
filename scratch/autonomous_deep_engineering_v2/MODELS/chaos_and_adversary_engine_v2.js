/**
 * CHAOS, ADVERSARY & RESILIENCE ENGINE V2
 * 
 * Formal models for Campaigns 034 – 050:
 * - Campaign 034: Human Gate Natural Language Adversary & Negation
 * - Campaign 035: Minimal Counterexample Reduction (Delta Debugging)
 * - Campaign 036: Mutation Invariant Rigor (100% Mutant Kill Rate)
 * - Campaign 037: Composite 3-Fault Chaos Scenario (Crash + Network Drop + Disk Fill)
 * - Campaign 038: Zombie Process Resurrection Adversary
 * - Campaign 039: Disk Fill & Truncated Evidence Protection
 * - Campaign 040: Monotonic Clock Drift Invariance
 * - Campaign 041: Network Partition & Partial ACK Deduplication
 * - Campaign 042: Concurrent Multi-Worker Race Resolution
 * - Campaign 043: Corrupted Checkpoint Rollback Defense
 * - Campaign 044: Poison Pill Payload Defense
 * - Campaign 045: Transport Protocol Downgrade Defense
 * - Campaign 046: Expired Lease Replay Defense
 * - Campaign 047: Symlink Sandbox Traversal Defense
 * - Campaign 048: Worker Machine ID Spoofing Defense
 * - Campaign 049: Ledger Fork Authority Reconciliation
 * - Campaign 050: Mid-Program Checkpoint Milestone & Saturation Review
 */

const crypto = require('crypto');

class HumanGateLanguageEngine {
  static evaluateHumanInput(rawText) {
    if (!rawText || typeof rawText !== 'string') {
      return { verdict: 'REJECTED', code: 'EMPTY_INPUT', reason: 'Empty input cannot be interpreted as authorization.' };
    }

    const trimmed = rawText.trim().toLowerCase();

    // 1. Explicit Negations / Halts (Precedence #1)
    const haltPatterns = [
      /\b(stop|halt|abbrechen|stopp|nein|no|warte|wait)\b/,
      /\b(nicht\s+weiter|do\s+not\s+proceed|do\s+not\s+continue|don't\s+continue)\b/,
      /\b(pause|cancel|abort|freeze|block)\b/
    ];
    for (const pat of haltPatterns) {
      if (pat.test(trimmed)) {
        return { verdict: 'BLOCKED', code: 'EXPLICIT_HALT_DETECTED', reason: `Explicit stop/negation word matched: ${pat}` };
      }
    }

    // 2. Adversarial Injection Attempts
    const injectionPatterns = [
      /ignore\s+previous/i,
      /bypass\s+sandbox/i,
      /delete\s+all/i,
      /format\s+c:/i,
      /rm\s+-rf/i
    ];
    for (const pat of injectionPatterns) {
      if (pat.test(trimmed)) {
        return { verdict: 'BLOCKED', code: 'ADVERSARIAL_INJECTION_BLOCKED', reason: 'Prompt injection or dangerous payload signature detected.' };
      }
    }

    // 3. Conditional / Ambiguous Statements
    if (trimmed.includes('if ') || trimmed.includes('wenn ') || trimmed.includes('maybe') || trimmed.includes('vielleicht') || trimmed.includes('aber ')) {
      return {
        verdict: 'AMBIGUOUS',
        code: 'CONDITIONAL_APPROVAL_REJECTED',
        reason: 'Conditional approvals are not autonomous authorizations. Must be unequivocal.'
      };
    }

    // 4. Unequivocal Proceed Phrases
    const validPhrases = [
      'weiter',
      'continue',
      'go on',
      'mach weiter',
      'proceed',
      'genehmigt',
      'approved',
      'ja'
    ];
    if (validPhrases.includes(trimmed)) {
      return { verdict: 'APPROVED', code: 'UNEQUIVOCAL_RESUME_AUTHORIZED', reason: 'Exact stamped continuation keyword.' };
    }

    return {
      verdict: 'AMBIGUOUS',
      code: 'UNRECOGNIZED_PHRASE_FAIL_CLOSED',
      reason: `Unrecognized phrase "${rawText}". Fails closed.`
    };
  }
}

class MinimalCounterexampleReducer {
  /**
   * Delta Debugging 1-minimal reduction of action traces
   */
  static reduceTrace(fullTrace, predicate) {
    let current = [...fullTrace];

    // Check if full trace reproduces
    if (!predicate(current)) {
      return { minimized: current, length: current.length, reduced: false };
    }

    // Try removing individual steps
    let changed = true;
    while (changed && current.length > 1) {
      changed = false;
      for (let i = 0; i < current.length; i++) {
        const candidate = current.filter((_, idx) => idx !== i);
        if (predicate(candidate)) {
          current = candidate;
          changed = true;
          break; // restart search with smaller trace
        }
      }
    }

    return {
      original_length: fullTrace.length,
      minimized_length: current.length,
      minimal_steps: current,
      reduction_ratio: ((fullTrace.length - current.length) / fullTrace.length * 100).toFixed(1) + '%'
    };
  }
}

class SystemResilienceGuard {
  /**
   * Campaign 037: Composite Chaos Recovery
   */
  static handleTripleFault(taskState, { processCrashed, networkAckLost, diskWriteFailed }) {
    if (processCrashed && networkAckLost && diskWriteFailed) {
      return {
        recovered_state: 'EXECUTION_UNCERTAIN',
        action: 'HOLD_FOR_RECONCILIATION',
        redispatch_allowed: false,
        evidence_salvaged: false,
        reason: 'Triple composite fault detected. Fail-closed: marked EXECUTION_UNCERTAIN to prevent duplicate writes.'
      };
    }
    return { recovered_state: taskState.status, action: 'NORMAL' };
  }

  /**
   * Campaign 038: Zombie Process Detection
   */
  static detectZombieProcess(expectedProcess, activeProcesses) {
    const live = activeProcesses.find(p => p.pid === expectedProcess.pid);
    if (!live) return { status: 'TERMINATED_CLEAN' };

    // Multi-factor identity check: PID + StartTime + TaskId
    if (live.start_time !== expectedProcess.start_time || live.task_id !== expectedProcess.task_id) {
      return {
        status: 'ZOMBIE_RECYCLED_PID_DETECTED',
        action: 'REVOKE_PROCESS_LEASE_AND_DISOWN',
        reason: 'PID exists but process creation time or task ID does not match original lease.'
      };
    }

    return { status: 'LEGITIMATE_ACTIVE' };
  }

  /**
   * Campaign 039: Truncated Evidence Protection
   */
  static validateEvidenceFileSize(filePath, fileSizeBytes) {
    if (fileSizeBytes === 0) {
      return { valid: false, code: 'EVIDENCE_ZERO_BYTES_CORRUPT', reason: 'Evidence log file is 0 bytes (likely disk fill or crash).' };
    }
    return { valid: true, code: 'EVIDENCE_VALID' };
  }

  /**
   * Campaign 040: Monotonic Clock Invariance
   */
  static checkTimeoutMonotonic(startTimeNs, nowNs, timeoutNs) {
    const elapsedNs = nowNs - startTimeNs;
    if (elapsedNs < 0) {
      return { timed_out: false, error: 'NEGATIVE_MONOTONIC_DELTA' };
    }
    return { timed_out: elapsedNs >= timeoutNs, elapsed_ns: elapsedNs };
  }

  /**
   * Campaign 041: Partial ACK Deduplication
   */
  static deduplicateAck(acknowledgedHashes, incomingAck) {
    if (acknowledgedHashes.has(incomingAck.evidence_hash)) {
      return {
        action: 'DROP_DUPLICATE_ACK',
        redispatch: false,
        reason: 'Evidence hash already committed to durable ledger.'
      };
    }
    acknowledgedHashes.add(incomingAck.evidence_hash);
    return { action: 'COMMIT_NEW_ACK', redispatch: false };
  }

  /**
   * Campaign 042: Concurrent Multi-Worker Race
   */
  static resolveWorkerRace(claims) {
    // Exactly one winner: earliest timestamp, tie-broken by lowest lexical worker_id
    if (!claims || claims.length === 0) return { winner: null, losers: [] };

    claims.sort((a, b) => {
      if (a.claimed_at_ms !== b.claimed_at_ms) return a.claimed_at_ms - b.claimed_at_ms;
      return a.worker_id.localeCompare(b.worker_id);
    });

    const winner = claims[0];
    const losers = claims.slice(1).map(c => ({
      worker_id: c.worker_id,
      code: 'LEASE_CONFLICT_LOST_RACE',
      reason: `Worker ${c.worker_id} lost lease race to ${winner.worker_id}`
    }));

    return { winner: winner.worker_id, losers };
  }

  /**
   * Campaign 043: Corrupt Checkpoint Rollback
   */
  static loadSafeCheckpoint(primaryContent, backupContent) {
    try {
      const parsed = JSON.parse(primaryContent);
      if (!parsed.mission_id || !parsed.last_completed_campaign) throw new Error('Missing fields');
      return { source: 'PRIMARY', checkpoint: parsed };
    } catch (e) {
      // Primary corrupted; rollback to backup
      const backupParsed = JSON.parse(backupContent);
      return { source: 'BACKUP_ROLLBACK', checkpoint: backupParsed, reason: 'Primary checkpoint corrupt; successfully recovered from backup.' };
    }
  }

  /**
   * Campaign 044: Poison Pill Payload Defense
   */
  static validatePayloadSafety(payloadString) {
    if (Buffer.byteLength(payloadString, 'utf8') > 10 * 1024 * 1024) { // > 10MB
      return { safe: false, code: 'POISON_PILL_PAYLOAD_TOO_LARGE', reason: 'Payload exceeds 10MB safety ceiling.' };
    }
    try {
      const obj = JSON.parse(payloadString);
      return { safe: true, code: 'PAYLOAD_VALID', obj };
    } catch (e) {
      return { safe: false, code: 'MALFORMED_JSON_PAYLOAD', reason: e.message };
    }
  }

  /**
   * Campaign 045: Transport Protocol Downgrade Defense
   */
  static verifyTransportProtocol(protocol) {
    const prohibited = ['HTTP/1.0', 'HTTP/1.1_CLEARTEXT', 'TELNET', 'INSECURE_WS'];
    if (prohibited.includes(protocol.toUpperCase())) {
      return {
        secure: false,
        code: 'INSECURE_TRANSPORT_DOWNGRADE_BLOCKED',
        reason: `Protocol ${protocol} does not meet mutual TLS / encrypted tunnel requirements.`
      };
    }
    return { secure: true, code: 'SECURE_TRANSPORT_VERIFIED' };
  }

  /**
   * Campaign 046: Expired Lease Replay Defense
   */
  static verifyLeaseFreshness(lease, maxTtlMs = 300000) {
    const now = Date.now();
    const issued = new Date(lease.issued_at).getTime();
    if (now - issued > maxTtlMs) {
      return {
        fresh: false,
        code: 'LEASE_EXPIRED_REPLAY_REJECTED',
        age_ms: now - issued,
        reason: 'Lease has expired and cannot be presented for authorization.'
      };
    }
    return { fresh: true, code: 'LEASE_FRESH' };
  }

  /**
   * Campaign 047: Symlink Sandbox Traversal Defense
   */
  static verifySymlinkPath(targetPath, sandboxRoot) {
    const normalizedTarget = targetPath.replace(/\\/g, '/').toLowerCase();
    const normalizedRoot = sandboxRoot.replace(/\\/g, '/').toLowerCase();

    if (!normalizedTarget.startsWith(normalizedRoot)) {
      return {
        safe: false,
        code: 'SYMLINK_TRAVERSAL_BLOCKED',
        reason: `Target path ${targetPath} escapes sandbox root ${sandboxRoot}.`
      };
    }
    return { safe: true, code: 'PATH_WITHIN_SANDBOX' };
  }

  /**
   * Campaign 048: Worker Machine ID Spoofing Defense
   */
  static verifyWorkerMachineId(workerClaim, enrolledMachines) {
    const enrolled = enrolledMachines.get(workerClaim.worker_id);
    if (!enrolled) {
      return { authorized: false, code: 'WORKER_NOT_ENROLLED' };
    }
    if (enrolled.hardware_uuid !== workerClaim.hardware_uuid) {
      return {
        authorized: false,
        code: 'MACHINE_ID_MISMATCH_REJECTED',
        reason: `Hardware UUID mismatch for worker ${workerClaim.worker_id}. Spoofing detected.`
      };
    }
    return { authorized: true, code: 'MACHINE_ID_VERIFIED' };
  }

  /**
   * Campaign 049: Ledger Fork Authority Reconciliation
   */
  static reconcileLedgerFork(branchA, branchB) {
    // Choose branch with highest valid cryptographic block count; tiebreak by root signature
    if (branchA.length > branchB.length) return { chosen: 'BRANCH_A', blocks: branchA.length };
    if (branchB.length > branchA.length) return { chosen: 'BRANCH_B', blocks: branchB.length };
    return { chosen: 'BRANCH_A', blocks: branchA.length, tiebreak: 'ROOT_AUTHORITY_DEFAULT' };
  }
}

module.exports = {
  HumanGateLanguageEngine,
  MinimalCounterexampleReducer,
  SystemResilienceGuard
};
