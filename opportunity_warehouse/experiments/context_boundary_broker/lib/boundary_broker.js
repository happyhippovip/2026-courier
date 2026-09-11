/**
 * Dynamic Context Window Boundary Negotiator & Token Allocation Broker
 * Brokers token budgets across collaborating multi-agent roles with guaranteed minimums
 * and priority-weighted surplus sharing.
 */

class ContextBoundaryBroker {
  constructor(totalCapacity = 128000, reservedBuffer = 4000) {
    this.totalCapacity = totalCapacity;
    this.reservedBuffer = reservedBuffer;
    this.agents = new Map(); // id -> { id, role, priorityWeight, minTokens, requestedTokens }
  }

  registerAgent(id, options = {}) {
    if (this.agents.has(id)) {
      throw new Error('Agent already registered: ' + id);
    }
    const agent = {
      id,
      role: options.role || 'worker',
      priorityWeight: options.priorityWeight || 1.0, // 1.0 to 10.0
      minTokens: options.minTokens || 1000,
      requestedTokens: options.requestedTokens || options.minTokens || 1000
    };
    this.agents.set(id, agent);
    return agent;
  }

  allocateBudget() {
    const usableCapacity = this.totalCapacity - this.reservedBuffer;
    let sumMin = 0;
    for (const a of this.agents.values()) {
      sumMin += a.minTokens;
    }

    if (sumMin > usableCapacity) {
      throw new Error('Total minimum token reservations exceed usable window capacity');
    }

    const surplusTokens = usableCapacity - sumMin;
    const allocations = new Map();

    // Step 1: Assign minimums
    for (const [id, a] of this.agents.entries()) {
      allocations.set(id, a.minTokens);
    }

    // Step 2: Compute surplus demand per agent
    let totalWeightedDemand = 0;
    const extraDemands = new Map();

    for (const [id, a] of this.agents.entries()) {
      const extraNeeded = Math.max(0, a.requestedTokens - a.minTokens);
      const weightedNeed = extraNeeded * a.priorityWeight;
      extraDemands.set(id, { extraNeeded, weightedNeed });
      totalWeightedDemand += weightedNeed;
    }

    // Step 3: Distribute surplus
    if (totalWeightedDemand > 0 && surplusTokens > 0) {
      for (const [id, dem] of extraDemands.entries()) {
        const share = (dem.weightedNeed / totalWeightedDemand) * surplusTokens;
        const grantedExtra = Math.min(dem.extraNeeded, Math.floor(share));
        allocations.set(id, allocations.get(id) + grantedExtra);
      }
    }

    let allocatedTotal = 0;
    const manifest = [];
    for (const [id, a] of this.agents.entries()) {
      const allocated = allocations.get(id);
      allocatedTotal += allocated;
      manifest.push({
        agentId: id,
        role: a.role,
        priorityWeight: a.priorityWeight,
        minTokens: a.minTokens,
        requestedTokens: a.requestedTokens,
        allocatedTokens: allocated,
        fulfillmentPercent: Number(((allocated / a.requestedTokens) * 100).toFixed(1))
      });
    }

    return {
      totalCapacity: this.totalCapacity,
      reservedBuffer: this.reservedBuffer,
      usableCapacity,
      allocatedTotal,
      freeCapacity: usableCapacity - allocatedTotal,
      agentAllocations: manifest
    };
  }

  yieldTokens(agentId, tokensToYield) {
    if (!this.agents.has(agentId)) throw new Error('Agent not found: ' + agentId);
    const a = this.agents.get(agentId);
    const newRequested = Math.max(a.minTokens, a.requestedTokens - tokensToYield);
    a.requestedTokens = newRequested;
    return this.allocateBudget();
  }

  requestSurge(agentId, additionalTokens) {
    if (!this.agents.has(agentId)) throw new Error('Agent not found: ' + agentId);
    const a = this.agents.get(agentId);
    a.requestedTokens += additionalTokens;
    return this.allocateBudget();
  }
}

module.exports = { ContextBoundaryBroker };
