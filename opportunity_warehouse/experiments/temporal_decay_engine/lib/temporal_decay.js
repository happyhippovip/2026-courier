/**
 * Context Window Temporal Decay & Semantic Forgetfulness Engine
 * Models memory relevance degradation over conversation turns using exponential half-life decay.
 * Evicts obsolete intermediate thoughts while permanently anchoring invariants.
 */

class TemporalDecayEngine {
  constructor(defaultHalfLifeTurns = 5) {
    this.defaultHalfLifeTurns = defaultHalfLifeTurns;
    this.memories = new Map(); // id -> { id, content, turnCreated, halfLifeTurns, isPermanent, isSuperceded }
  }

  addMemory(id, content = '', turnCreated = 1, options = {}) {
    const memory = {
      id,
      content,
      turnCreated,
      halfLifeTurns: options.isPermanent ? Infinity : (options.halfLifeTurns || this.defaultHalfLifeTurns),
      isPermanent: options.isPermanent || false,
      isSuperceded: false,
      tokens: Math.max(1, Math.round(content.length / 4))
    };
    this.memories.set(id, memory);
    return memory;
  }

  markSuperceded(id) {
    if (this.memories.has(id)) {
      const m = this.memories.get(id);
      m.isSuperceded = true;
    }
  }

  calculateRetentionWeight(memory, currentTurn) {
    if (memory.isPermanent) return 1.0;
    if (memory.isSuperceded) return 0.0;

    const ageTurns = Math.max(0, currentTurn - memory.turnCreated);
    // Exponential decay formula: W = 2 ^ (-age / halfLife)
    const weight = Math.pow(2, -ageTurns / memory.halfLifeTurns);
    return Number(weight.toFixed(3));
  }

  compactMemories(currentTurn, evictionThreshold = 0.25) {
    const retained = [];
    const evicted = [];
    let origTokens = 0;
    let finalTokens = 0;

    for (const m of this.memories.values()) {
      origTokens += m.tokens;
      const weight = this.calculateRetentionWeight(m, currentTurn);

      if (weight >= evictionThreshold) {
        finalTokens += m.tokens;
        retained.push({
          id: m.id,
          weight,
          content: m.content
        });
      } else {
        evicted.push({
          id: m.id,
          weight,
          reason: m.isSuperceded ? 'SUPERCEDED_BY_NEWER_TURN' : 'TEMPORAL_DECAY_BELOW_THRESHOLD'
        });
      }
    }

    return {
      currentTurn,
      originalTokens: origTokens,
      finalTokens: finalTokens,
      tokensSaved: origTokens - finalTokens,
      savingsPercent: origTokens > 0 ? Number((((origTokens - finalTokens) / origTokens) * 100).toFixed(1)) : 0,
      retainedCount: retained.length,
      evictedCount: evicted.length,
      retainedMemories: retained,
      evictedMemories: evicted
    };
  }
}

module.exports = { TemporalDecayEngine };
