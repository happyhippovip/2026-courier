/**
 * Multi-Tenant Context Window Fair-Share Deficit Round-Robin (DRR) Scheduler
 * Implements Shreedhar & Varghese Deficit Round-Robin queuing for token quota allocation,
 * ensuring strict starvation avoidance, weighted fair-share throughput, and O(1) scheduling.
 */

class DRRContextScheduler {
  constructor(options = {}) {
    this.quantumBase = options.quantumBase || 100; // base token allocation per round
    this.globalTokenCapacity = options.globalTokenCapacity || 10000;
    this.tenants = new Map(); // tenantId -> { weight, quantum, deficit, queue: [] }
    this.activeList = []; // list of tenantIds with non-empty queues
  }

  registerTenant(tenantId, weight = 1) {
    const quantum = Math.floor(this.quantumBase * weight);
    this.tenants.set(tenantId, {
      tenantId,
      weight,
      quantum,
      deficit: 0,
      queue: [],
      servedTokens: 0,
      servedRequests: 0
    });
  }

  enqueueRequest(tenantId, request) {
    if (!this.tenants.has(tenantId)) {
      this.registerTenant(tenantId, 1);
    }
    const tenant = this.tenants.get(tenantId);
    tenant.queue.push({
      id: request.id || ('req_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6)),
      tokenCost: request.tokenCost || 1,
      payload: request.payload || null,
      enqueuedAt: Date.now()
    });

    if (!this.activeList.includes(tenantId)) {
      this.activeList.push(tenantId);
    }
  }

  scheduleRound(maxTokensInRound = this.globalTokenCapacity) {
    const servedInRound = [];
    let tokensDispatched = 0;
    const currentActive = [...this.activeList];

    for (const tenantId of currentActive) {
      if (tokensDispatched >= maxTokensInRound) break;

      const tenant = this.tenants.get(tenantId);
      tenant.deficit += tenant.quantum;

      while (tenant.queue.length > 0) {
        const nextReq = tenant.queue[0];
        if (nextReq.tokenCost <= tenant.deficit) {
          if (tokensDispatched + nextReq.tokenCost > maxTokensInRound) {
            break;
          }

          tenant.queue.shift();
          tenant.deficit -= nextReq.tokenCost;
          tenant.servedTokens += nextReq.tokenCost;
          tenant.servedRequests++;
          tokensDispatched += nextReq.tokenCost;

          servedInRound.push({
            tenantId,
            requestId: nextReq.id,
            tokens: nextReq.tokenCost,
            remainingDeficit: tenant.deficit
          });
        } else {
          break;
        }
      }

      if (tenant.queue.length === 0) {
        tenant.deficit = 0;
        const idx = this.activeList.indexOf(tenantId);
        if (idx !== -1) {
          this.activeList.splice(idx, 1);
        }
      }
    }

    return {
      tokensDispatched,
      requestsServed: servedInRound.length,
      dispatched: servedInRound
    };
  }

  drain(maxTokens = this.globalTokenCapacity, maxRounds = 50) {
    let totalTokens = 0;
    let totalRequests = 0;
    let roundCount = 0;
    while (this.activeList.length > 0 && totalTokens < maxTokens && roundCount < maxRounds) {
      const res = this.scheduleRound(maxTokens - totalTokens);
      if (res.requestsServed === 0 && res.tokensDispatched === 0) {
        break;
      }
      totalTokens += res.tokensDispatched;
      totalRequests += res.requestsServed;
      roundCount++;
    }
    return { totalTokens, totalRequests, rounds: roundCount };
  }

  calculateJainsFairnessIndex() {
    const served = Array.from(this.tenants.values()).map(t => {
      // Normalized served tokens by weight
      return t.weight > 0 ? (t.servedTokens / t.weight) : 0;
    });

    const n = served.length;
    if (n === 0) return 1.0;

    const sum = served.reduce((acc, x) => acc + x, 0);
    const sumSq = served.reduce((acc, x) => acc + x * x, 0);

    if (sumSq === 0) return 1.0;
    return Number(((sum * sum) / (n * sumSq)).toFixed(4));
  }

  getTenantStats() {
    const stats = {};
    for (const [id, t] of this.tenants.entries()) {
      stats[id] = {
        weight: t.weight,
        quantum: t.quantum,
        deficit: t.deficit,
        queueLength: t.queue.length,
        servedTokens: t.servedTokens,
        servedRequests: t.servedRequests
      };
    }
    return stats;
  }
}

module.exports = { DRRContextScheduler };
