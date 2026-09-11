/**
 * Multi-Agent State Synchronization Vector Clock & Causality Graph Engine
 * Tracks causal ordering (happens-before) across distributed autonomous agents,
 * detecting concurrency, resolving state divergences, and establishing deterministic replay DAGs.
 */

class VectorClock {
  constructor(agentId, clockMap = {}) {
    this.agentId = agentId;
    this.clock = { ...clockMap };
    if (this.agentId && this.clock[this.agentId] === undefined) {
      this.clock[this.agentId] = 0;
    }
  }

  tick() {
    if (this.agentId) {
      this.clock[this.agentId] = (this.clock[this.agentId] || 0) + 1;
    }
    return this.clone();
  }

  send() {
    this.tick();
    return this.clone();
  }

  receive(senderClock) {
    for (const [id, count] of Object.entries(senderClock.clock || senderClock)) {
      this.clock[id] = Math.max(this.clock[id] || 0, count);
    }
    this.tick();
    return this.clone();
  }

  clone() {
    return new VectorClock(this.agentId, { ...this.clock });
  }

  static compare(v1, v2) {
    const c1 = v1.clock || v1;
    const c2 = v2.clock || v2;
    const allKeys = new Set([...Object.keys(c1), ...Object.keys(c2)]);

    let v1Greater = false;
    let v2Greater = false;

    for (const k of allKeys) {
      const val1 = c1[k] || 0;
      const val2 = c2[k] || 0;
      if (val1 > val2) v1Greater = true;
      if (val2 > val1) v2Greater = true;
    }

    if (!v1Greater && !v2Greater) return 'IDENTICAL';
    if (v1Greater && !v2Greater) return 'HAPPENS_AFTER'; // v1 happened after v2
    if (!v1Greater && v2Greater) return 'HAPPENS_BEFORE'; // v1 happened before v2
    return 'CONCURRENT'; // v1 and v2 happened concurrently
  }

  static resolveConflict(eventA, eventB) {
    // If one happens before the other, latest wins
    const rel = VectorClock.compare(eventA.clock, eventB.clock);
    if (rel === 'HAPPENS_AFTER') return { winner: eventA, reason: 'CAUSALLY_DOMINANT' };
    if (rel === 'HAPPENS_BEFORE') return { winner: eventB, reason: 'CAUSALLY_DOMINANT' };

    // Concurrent: deterministic tie-breaking by clock sum, then agentId lexicographical
    const sumA = Object.values(eventA.clock.clock || eventA.clock).reduce((a, b) => a + b, 0);
    const sumB = Object.values(eventB.clock.clock || eventB.clock).reduce((a, b) => a + b, 0);

    if (sumA !== sumB) {
      return { winner: sumA > sumB ? eventA : eventB, reason: 'HIGHER_LOGICAL_SUM' };
    }

    // Tie-break by agentId
    const winner = eventA.agentId < eventB.agentId ? eventA : eventB;
    return { winner, reason: 'DETERMINISTIC_AGENT_ID_TIEBREAK' };
  }
}

module.exports = { VectorClock };
