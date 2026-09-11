/**
 * Context Window Token Budget Slicing & Sliding Window Reservoir
 * Implements priority-weighted decay reservoir sampling to bound continuous
 * event streams within a finite token budget while permanently retaining core anchors.
 */

class SlidingWindowReservoir {
  constructor(maxBudgetTokens = 10000) {
    this.maxBudgetTokens = maxBudgetTokens;
    this.events = []; // { id, priority, tokens, timestamp, payload, isAnchor }
  }

  addEvent(id, priority = 'medium', tokens = 100, payload = '', isAnchor = false) {
    const event = {
      id,
      priority, // 'critical', 'high', 'medium', 'low'
      tokens,
      timestamp: Date.now(),
      payload,
      isAnchor
    };

    this.events.push(event);
    this.rebalanceReservoir();
    return event;
  }

  getCurrentTokenTotal() {
    return this.events.reduce((acc, e) => acc + e.tokens, 0);
  }

  rebalanceReservoir() {
    let currentTokens = this.getCurrentTokenTotal();
    if (currentTokens <= this.maxBudgetTokens) return;

    // Eviction candidate priority ordering:
    // 1. Anchors are NEVER evicted
    // 2. Critical events are evicted last
    // 3. Low priority events are evicted first (oldest first within priority)

    const priorityRank = { 'low': 1, 'medium': 2, 'high': 3, 'critical': 4 };

    while (currentTokens > this.maxBudgetTokens && this.events.length > 1) {
      // Find lowest priority non-anchor event
      let candidateIdx = -1;
      let lowestRank = Infinity;

      for (let i = 0; i < this.events.length; i++) {
        const ev = this.events[i];
        if (ev.isAnchor) continue; // skip anchors

        const rank = priorityRank[ev.priority] || 2;
        if (rank < lowestRank) {
          lowestRank = rank;
          candidateIdx = i;
        }
      }

      if (candidateIdx === -1) {
        // Only anchors remain; cannot evict further
        break;
      }

      const evicted = this.events.splice(candidateIdx, 1)[0];
      currentTokens -= evicted.tokens;
    }
  }

  generateReservoirReport() {
    const totalTokens = this.getCurrentTokenTotal();
    return {
      maxBudgetTokens: this.maxBudgetTokens,
      totalTokens,
      utilizationPercent: Number(((totalTokens / this.maxBudgetTokens) * 100).toFixed(1)),
      eventCount: this.events.length,
      anchorsCount: this.events.filter(e => e.isAnchor).length,
      events: this.events
    };
  }
}

module.exports = { SlidingWindowReservoir };
