'use strict';

const crypto = require('crypto');

/**
 * ResultCustoms
 * Gatekeeper for worker deliverables and task completion verdicts.
 * Ensures no result enters the persistent record without meeting
 * cryptographic, structural, and invariant standards.
 */
class ResultCustoms {
  constructor(options = {}) {
    this.allowedStatuses = new Set(['SUCCESS', 'FAILURE', 'BLOCKED', 'FATAL']);
    this.minSchemaVersion = options.minSchemaVersion || 2;
    this.clearedResults = new Map(); // logical_work_id -> cleared result
  }

  computeProofHash(proofPackage) {
    if (!proofPackage) return null;
    const canonical = JSON.stringify({
      assertions_run: proofPackage.assertions_run || 0,
      artifacts_produced: (proofPackage.artifacts_produced || []).sort(),
      verification_signature: proofPackage.verification_signature || ''
    });
    return crypto.createHash('sha256').update(canonical).digest('hex');
  }

  inspectResult(resultPayload) {
    const violations = [];

    if (!resultPayload || typeof resultPayload !== 'object') {
      return {
        cleared: false,
        reason: 'INVALID_PAYLOAD_STRUCTURE',
        violations: ['Payload must be a non-null object']
      };
    }

    const {
      task_id,
      logical_work_id,
      worker_id,
      status,
      proof_package,
      artifacts = [],
      schema_version = 1,
      is_read_only = false
    } = resultPayload;

    if (!task_id || typeof task_id !== 'string') {
      violations.push('MISSING_TASK_ID');
    }
    if (!logical_work_id || typeof logical_work_id !== 'string') {
      violations.push('MISSING_LOGICAL_WORK_ID');
    }
    if (!worker_id || typeof worker_id !== 'string') {
      violations.push('MISSING_WORKER_ID');
    }

    if (!this.allowedStatuses.has(status)) {
      violations.push(`INVALID_STATUS: ${status}`);
    }

    if (schema_version < this.minSchemaVersion) {
      violations.push(`OBSOLETE_SCHEMA_VERSION: ${schema_version} < ${this.minSchemaVersion}`);
    }

    // Success invariant checks
    if (status === 'SUCCESS') {
      if (!proof_package || typeof proof_package !== 'object') {
        violations.push('SUCCESS_REQUIRES_PROOF_PACKAGE');
      } else {
        if (typeof proof_package.assertions_run !== 'number' || proof_package.assertions_run <= 0) {
          violations.push('SUCCESS_REQUIRES_POSITIVE_ASSERTION_COUNT');
        }

        const expectedHash = this.computeProofHash(proof_package);
        if (!proof_package.proof_hash || proof_package.proof_hash !== expectedHash) {
          violations.push(`PROOF_HASH_MISMATCH: got ${proof_package.proof_hash}, expected ${expectedHash}`);
        }
      }

      // Non-empty deliverable invariant (unless task was declared read-only)
      if (!is_read_only && (!artifacts || artifacts.length === 0)) {
        violations.push('SUCCESS_REQUIRES_NON_EMPTY_ARTIFACTS');
      }

      // Validate artifacts
      if (Array.isArray(artifacts)) {
        for (let i = 0; i < artifacts.length; i++) {
          const art = artifacts[i];
          if (!art.path || typeof art.path !== 'string') {
            violations.push(`ARTIFACT_${i}_MISSING_PATH`);
          }
          if (!art.sha256 || typeof art.sha256 !== 'string' || art.sha256.length !== 64) {
            violations.push(`ARTIFACT_${i}_INVALID_SHA256`);
          }
          if (typeof art.bytes !== 'number' || art.bytes < 0) {
            violations.push(`ARTIFACT_${i}_INVALID_BYTE_COUNT`);
          }
        }
      }
    }

    if (violations.length > 0) {
      return {
        cleared: false,
        reason: 'CUSTOMS_REJECTED',
        violations
      };
    }

    // Check concurrency and idempotency
    const existing = this.clearedResults.get(logical_work_id);
    if (existing) {
      if (existing.result_hash === this._hashResult(resultPayload)) {
        return {
          cleared: true,
          idempotent_duplicate: true,
          verdict: 'CLEARED_DUPLICATE',
          logical_work_id
        };
      } else {
        return {
          cleared: false,
          reason: 'CONFLICTING_RESULT_ALREADY_CLEARED',
          violations: [`Conflicting result already cleared for logical_work_id: ${logical_work_id}`]
        };
      }
    }

    const clearedRecord = {
      ...resultPayload,
      cleared_at_ms: Date.now(),
      result_hash: this._hashResult(resultPayload)
    };
    this.clearedResults.set(logical_work_id, clearedRecord);

    return {
      cleared: true,
      idempotent_duplicate: false,
      verdict: 'CLEARED_NEW',
      logical_work_id,
      result_hash: clearedRecord.result_hash
    };
  }

  _hashResult(payload) {
    return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  }
}

module.exports = { ResultCustoms };
