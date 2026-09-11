/**
 * Dynamic Context Window Slot Allocator & Quota Bin-Packer
 * Dynamically partitions constrained LLM context windows among competing components
 * (system prompt, conversation history, RAG documents, tool schemas, response headroom),
 * prioritizing guaranteed minimums and bin-packing elastic requests to guarantee 0 overflow errors.
 */

class ContextSlotAllocator {
  constructor() {}

  allocateSlots(totalBudget = 8192, requests = []) {
    // requests: Array of { id, priority, minTokens, requestedTokens }
    // priority: higher number = higher priority (e.g. 10 = critical, 1 = optional)

    const allocations = {};
    let remainingBudget = totalBudget;

    // Phase 1: Allocate guaranteed minimums in priority order
    const sortedByPriority = [...requests].sort((a, b) => b.priority - a.priority);

    for (const req of sortedByPriority) {
      const guaranteed = Math.min(req.minTokens, remainingBudget);
      allocations[req.id] = guaranteed;
      remainingBudget -= guaranteed;
    }

    // Phase 2: Distribute remaining budget to satisfy elastic requests
    for (const req of sortedByPriority) {
      if (remainingBudget <= 0) break;
      const needed = Math.max(0, req.requestedTokens - allocations[req.id]);
      const grant = Math.min(needed, remainingBudget);
      allocations[req.id] += grant;
      remainingBudget -= grant;
    }

    const totalAllocated = totalBudget - remainingBudget;
    const utilizationPercent = Number(((totalAllocated / totalBudget) * 100).toFixed(1));

    return {
      totalBudget,
      totalAllocated,
      remainingBudget,
      utilizationPercent,
      allocations,
      componentBreakdown: requests.map(r => ({
        id: r.id,
        priority: r.priority,
        minTokens: r.minTokens,
        requestedTokens: r.requestedTokens,
        allocatedTokens: allocations[r.id],
        satisfiedPercent: Number(((allocations[r.id] / r.requestedTokens) * 100).toFixed(1))
      }))
    };
  }
}

module.exports = { ContextSlotAllocator };