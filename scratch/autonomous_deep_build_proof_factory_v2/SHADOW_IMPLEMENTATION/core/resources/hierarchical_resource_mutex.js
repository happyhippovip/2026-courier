'use strict';

/**
 * SHADOW IMPLEMENTATION: HIERARCHICAL RESOURCE MUTEX (L01)
 * Component: shadow/core/resources/hierarchical_resource_mutex.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

const crypto = require('crypto');
const { PathNormalizer } = require('./path_normalizer');

class ResourceConflictError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'ResourceConflictError';
    this.details = details;
  }
}

class HierarchicalResourceMutex {
  constructor(options = {}) {
    this.normalizer = new PathNormalizer(options);
    this.activeLocks = new Map(); // resourceKey -> lockRecord
    this.waiters = [];
    this.agingRatePerSec = options.agingRatePerSec || 1.0;
  }

  canonicalizeResource(resourceType, resourceUri) {
    if (resourceType === 'FILE' || resourceType === 'TREE') {
      return {
        type: resourceType,
        key: `fs:${this.normalizer.normalize(resourceUri)}`,
        uri: this.normalizer.normalize(resourceUri)
      };
    }
    // Semantic non-filesystem resources
    return {
      type: resourceType,
      key: `${resourceType.toLowerCase()}:${(resourceUri || '').trim().toLowerCase()}`,
      uri: (resourceUri || '').trim().toLowerCase()
    };
  }

  isConflicting(reqType, reqUri, reqMode) {
    const canonicalReq = this.canonicalizeResource(reqType, reqUri);

    for (const [key, lock] of this.activeLocks.entries()) {
      if (reqType === 'FILE' || reqType === 'TREE') {
        if (lock.resourceType === 'FILE' || lock.resourceType === 'TREE') {
          // Check prefix collision
          if (this.normalizer.isPrefixCollision(canonicalReq.uri, lock.rawUri)) {
            if (reqMode === 'EXCLUSIVE' || lock.mode === 'EXCLUSIVE') {
              return { conflict: true, conflictingLock: lock };
            }
          }
        }
      } else {
        // Semantic resource (exact key match)
        if (key === canonicalReq.key) {
          if (reqMode === 'EXCLUSIVE' || lock.mode === 'EXCLUSIVE') {
            return { conflict: true, conflictingLock: lock };
          }
        }
      }
    }

    return { conflict: false };
  }

  acquireLock({
    taskId,
    resourceType = 'FILE',
    resourceUri,
    mode = 'EXCLUSIVE',
    priority = 5,
    ttlMs = null
  }) {
    const conflictCheck = this.isConflicting(resourceType, resourceUri, mode);

    if (conflictCheck.conflict) {
      const { conflictingLock } = conflictCheck;
      throw new ResourceConflictError(
        `[L01_RESOURCE_CONFLICT] Task '${taskId}' cannot acquire ${mode} lock on ${resourceType} '${resourceUri}'. Collides with active ${conflictingLock.mode} lock held by '${conflictingLock.holderTaskId}' on '${conflictingLock.rawUri}'.`,
        {
          requested: { taskId, resourceType, resourceUri, mode, priority },
          active: conflictingLock
        }
      );
    }

    const canonical = this.canonicalizeResource(resourceType, resourceUri);
    const now = Date.now();
    const lockRecord = {
      lockId: 'lock_' + crypto.randomBytes(6).toString('hex'),
      holderTaskId: taskId,
      holders: new Set([taskId]),
      mode,
      resourceType,
      rawUri: canonical.uri,
      resourceKey: canonical.key,
      priority,
      acquiredAt: now,
      ttlMs: ttlMs || null,
      expiresAt: ttlMs ? now + ttlMs : null
    };

    this.activeLocks.set(canonical.key, lockRecord);
    return lockRecord;
  }

  releaseLock(taskId, resourceType, resourceUri) {
    const canonical = this.canonicalizeResource(resourceType, resourceUri);
    const existing = this.activeLocks.get(canonical.key);

    if (!existing) return false;

    if (existing.holders.has(taskId)) {
      existing.holders.delete(taskId);
      if (existing.holders.size === 0) {
        this.activeLocks.delete(canonical.key);
      }
      return true;
    }

    return false;
  }

  releaseAllLocksForTask(taskId) {
    const released = [];
    for (const [key, lock] of Array.from(this.activeLocks.entries())) {
      if (lock.holders.has(taskId)) {
        lock.holders.delete(taskId);
        released.push(lock.rawUri);
        if (lock.holders.size === 0) {
          this.activeLocks.delete(key);
        }
      }
    }
    return released;
  }

  cleanupExpiredLocks(currentTimeMs = Date.now()) {
    const expiredKeys = [];
    for (const [key, lock] of this.activeLocks.entries()) {
      if (lock.expiresAt && currentTimeMs >= lock.expiresAt) {
        expiredKeys.push(key);
      }
    }
    for (const key of expiredKeys) {
      this.activeLocks.delete(key);
    }
    return expiredKeys;
  }

  cleanupExpiredLeases(currentTimeMs = Date.now()) {
    return this.cleanupExpiredLocks(currentTimeMs);
  }

  acquireLease(resourceUri, taskId, mode = 'WRITE', ttlMs = null) {
    try {
      const lock = this.acquireLock({
        taskId,
        resourceType: 'FILE',
        resourceUri,
        mode: mode === 'WRITE' ? 'EXCLUSIVE' : 'SHARED',
        ttlMs
      });
      return { granted: true, lease: { lease_id: lock.lockId, ...lock } };
    } catch (err) {
      if (err.name === 'ResourceConflictError') {
        return { granted: false, reason: 'EXCLUSIVE_LOCK_HELD', error: err.message };
      }
      throw err;
    }
  }

  releaseLease(leaseId, taskId) {
    return this.releaseAllLocksForTask(taskId);
  }

  getEffectivePriority(waiter, currentTime = Date.now()) {
    const waitSeconds = (currentTime - waiter.requestedAt) / 1000.0;
    return waiter.priority + (waitSeconds * this.agingRatePerSec);
  }
}

module.exports = {
  HierarchicalResourceMutex,
  ResourceConflictError
};
