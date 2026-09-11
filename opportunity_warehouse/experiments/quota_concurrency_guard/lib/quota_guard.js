class QuotaConcurrencyGuard {
  constructor(options = {}) {
    this.tier = options.tier || 'SOLO';
    this.limits = {
      SOLO: 1,
      TEAM: 5,
      ENTERPRISE: 25
    };
    this.maxConcurrent = options.maxConcurrent || this.limits[this.tier] || 1;
    this.activeWorkers = new Map();
  }

  acquireSlot(workerId, metadata = {}) {
    if (!workerId) throw new Error('workerId is required');

    // Clean up stale slots older than 5 minutes
    const now = Date.now();
    for (const [id, info] of this.activeWorkers.entries()) {
      if (now - info.timestamp > 300000) {
        this.activeWorkers.delete(id);
      }
    }

    if (this.activeWorkers.size >= this.maxConcurrent) {
      return {
        acquired: false,
        reason: 'CONCURRENCY_QUOTA_EXCEEDED',
        currentActive: this.activeWorkers.size,
        maxAllowed: this.maxConcurrent,
        tier: this.tier,
        upgradeRecommendation: this.tier === 'SOLO' ? 'Upgrade to TEAM for 5 seats' : 'Upgrade to ENTERPRISE for 25 seats'
      };
    }

    const slotInfo = {
      workerId,
      timestamp: now,
      metadata
    };
    this.activeWorkers.set(workerId, slotInfo);

    return {
      acquired: true,
      currentActive: this.activeWorkers.size,
      maxAllowed: this.maxConcurrent,
      tier: this.tier
    };
  }

  releaseSlot(workerId) {
    const deleted = this.activeWorkers.delete(workerId);
    return {
      released: deleted,
      remainingActive: this.activeWorkers.size
    };
  }
}

module.exports = { QuotaConcurrencyGuard };
