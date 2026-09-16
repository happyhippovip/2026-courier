'use strict';

const path = require('path');

/**
 * BorderGuard
 * Enforces strict boundary isolation for files, paths, network references,
 * and payloads entering or exiting task execution boundaries.
 */
class BorderGuard {
  constructor(options = {}) {
    this.allowedRoot = options.allowedRoot ? path.resolve(options.allowedRoot).toLowerCase() : null;
    this.trustedOrigins = new Set(options.trustedOrigins || ['COURIER_CORE', 'SUPERVISOR', 'LOCAL_WORKER']);
    this.maxPayloadBytes = options.maxPayloadBytes || 10 * 1024 * 1024; // 10MB
  }

  inspectPath(filePath) {
    if (!filePath || typeof filePath !== 'string') {
      return { allowed: false, reason: 'INVALID_PATH_TYPE', detail: 'Path must be a non-empty string' };
    }

    // Null bytes or control characters
    if (/[\x00-\x1f]/.test(filePath)) {
      return { allowed: false, reason: 'ILLEGAL_CONTROL_CHAR', detail: 'Path contains control characters or null bytes' };
    }

    // UNC paths
    if (filePath.startsWith('\\\\') || filePath.startsWith('//')) {
      return { allowed: false, reason: 'UNC_PATH_FORBIDDEN', detail: 'UNC network paths are prohibited' };
    }

    // Path traversal tokens
    const normalized = filePath.replace(/\\/g, '/');
    const segments = normalized.split('/');
    if (segments.includes('..')) {
      return { allowed: false, reason: 'PATH_TRAVERSAL_DETECTED', detail: 'Relative directory traversal (..) is strictly forbidden' };
    }

    // Root containment check if allowedRoot is configured
    if (this.allowedRoot) {
      const resolved = path.resolve(filePath).toLowerCase();
      if (!resolved.startsWith(this.allowedRoot)) {
        return { allowed: false, reason: 'BOUNDARY_ESCAPE_DETECTED', detail: `Path ${resolved} is outside allowed root ${this.allowedRoot}` };
      }
    }

    return { allowed: true, reason: 'PATH_CLEARED', normalizedPath: normalized };
  }

  inspectPayload(payload, metadata = {}) {
    const { origin = 'LOCAL_WORKER', sizeBytes = null } = metadata;

    if (!this.trustedOrigins.has(origin)) {
      return { allowed: false, reason: 'UNTRUSTED_ORIGIN', detail: `Origin '${origin}' is not in trusted set` };
    }

    const calculatedSize = sizeBytes !== null ? sizeBytes : Buffer.byteLength(typeof payload === 'string' ? payload : JSON.stringify(payload));
    if (calculatedSize > this.maxPayloadBytes) {
      return { allowed: false, reason: 'PAYLOAD_OVERSIZED', detail: `Size ${calculatedSize} exceeds limit ${this.maxPayloadBytes}` };
    }

    return { allowed: true, reason: 'PAYLOAD_CLEARED' };
  }

  inspectArtifacts(artifacts) {
    if (!Array.isArray(artifacts)) {
      return { allowed: false, reason: 'INVALID_ARTIFACTS_LIST', detail: 'Artifacts must be an array' };
    }

    for (let i = 0; i < artifacts.length; i++) {
      const art = artifacts[i];
      const pathVerdict = this.inspectPath(art.path);
      if (!pathVerdict.allowed) {
        return {
          allowed: false,
          reason: `ARTIFACT_VIOLATION_${pathVerdict.reason}`,
          detail: `Artifact [${i}] '${art.path}': ${pathVerdict.detail}`
        };
      }
      if (typeof art.bytes === 'number' && art.bytes > this.maxPayloadBytes) {
        return {
          allowed: false,
          reason: 'ARTIFACT_OVERSIZED',
          detail: `Artifact [${i}] exceeds maximum allowed size: ${art.bytes} bytes`
        };
      }
    }

    return { allowed: true, reason: 'ALL_ARTIFACTS_CLEARED' };
  }
}

module.exports = { BorderGuard };
