/**
 * Multi-Tenant Context Quota Rate Limiter & Token Leaky Bucket Daemon
 * Enforces per-tenant and per-agent token throughput rate limits using
 * the continuous leaky bucket algorithm.
 */

class ContextRateLimiter {
  constructor() {
    this.tenants = new Map();
  }

  registerTenant(tenantId, options = {}) {
    if (this.tenants.has(tenantId)) {
      throw new Error('Tenant already registered: ' + tenantId);
    }
    const capacity = options.capacity || 50000;
    const leakRatePerSec = options.leakRatePerSec || 5000;
    const initialTimestamp = options.initialTimestamp !== undefined ? options.initialTimestamp : Date.now();

    const tenant = {
      tenantId,
      capacity,
      fillLevel: 0,
      leakRatePerSec,
      lastLeakTimestamp: initialTimestamp,
      totalConsumed: 0,
      totalRejected: 0
    };
    this.tenants.set(tenantId, tenant);
    return tenant;
  }

  leak(tenant, now = Date.now()) {
    const elapsedSeconds = (now - tenant.lastLeakTimestamp) / 1000;
    if (elapsedSeconds > 0) {
      const leaked = elapsedSeconds * tenant.leakRatePerSec;
      tenant.fillLevel = Math.max(0, tenant.fillLevel - leaked);
      tenant.lastLeakTimestamp = now;
    }
  }

  consumeTokens(tenantId, tokensRequested = 1000, simulatedTime = Date.now()) {
    if (!this.tenants.has(tenantId)) {
      throw new Error('Tenant not found: ' + tenantId);
    }
    const tenant = this.tenants.get(tenantId);
    this.leak(tenant, simulatedTime);

    if (tenant.fillLevel + tokensRequested <= tenant.capacity) {
      tenant.fillLevel += tokensRequested;
      tenant.totalConsumed += tokensRequested;
      return {
        allowed: true,
        tenantId,
        tokensRequested,
        currentFillLevel: Math.round(tenant.fillLevel),
        capacity: tenant.capacity,
        remainingCapacity: Math.round(tenant.capacity - tenant.fillLevel),
        retryAfterMs: 0
      };
    } else {
      tenant.totalRejected += tokensRequested;
      const overflow = (tenant.fillLevel + tokensRequested) - tenant.capacity;
      const retryAfterSeconds = overflow / tenant.leakRatePerSec;
      return {
        allowed: false,
        tenantId,
        tokensRequested,
        currentFillLevel: Math.round(tenant.fillLevel),
        capacity: tenant.capacity,
        remainingCapacity: Math.round(tenant.capacity - tenant.fillLevel),
        retryAfterMs: Math.ceil(retryAfterSeconds * 1000)
      };
    }
  }

  generateAuditReport() {
    const report = [];
    for (const t of this.tenants.values()) {
      report.push({
        tenantId: t.tenantId,
        capacity: t.capacity,
        fillLevel: Math.round(t.fillLevel),
        leakRatePerSec: t.leakRatePerSec,
        totalConsumed: t.totalConsumed,
        totalRejected: t.totalRejected,
        rejectionRatePercent: (t.totalConsumed + t.totalRejected) > 0
          ? Number(((t.totalRejected / (t.totalConsumed + t.totalRejected)) * 100).toFixed(1))
          : 0
      });
    }
    return {
      activeTenants: this.tenants.size,
      timestamp: new Date().toISOString(),
      tenants: report
    };
  }
}

module.exports = { ContextRateLimiter };
