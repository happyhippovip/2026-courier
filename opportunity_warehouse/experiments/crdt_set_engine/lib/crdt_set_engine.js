/**
 * Multi-Agent Conflict-Free Replicated Data Type (CRDT) Engine
 * Implements State-Based CRDTs:
 * 1. PN-Counter (Positive-Negative Counter for distributed token accounting)
 * 2. OR-Set (Observed-Remove Set for distributed context tags)
 */

class PNCounter {
  constructor(nodeId) {
    this.nodeId = nodeId;
    this.p = new Map(); // nodeId -> count
    this.n = new Map(); // nodeId -> count
  }

  increment(amount = 1) {
    this.p.set(this.nodeId, (this.p.get(this.nodeId) || 0) + amount);
  }

  decrement(amount = 1) {
    this.n.set(this.nodeId, (this.n.get(this.nodeId) || 0) + amount);
  }

  value() {
    let pSum = 0;
    for (const v of this.p.values()) pSum += v;
    let nSum = 0;
    for (const v of this.n.values()) nSum += v;
    return pSum - nSum;
  }

  merge(other) {
    for (const [id, count] of other.p.entries()) {
      this.p.set(id, Math.max(this.p.get(id) || 0, count));
    }
    for (const [id, count] of other.n.entries()) {
      this.n.set(id, Math.max(this.n.get(id) || 0, count));
    }
  }
}

class ORSet {
  constructor() {
    this.addSet = new Map(); // tag -> element
    this.removeSet = new Set(); // tag
  }

  add(element) {
    const tag = element + ':' + Math.random().toString(36).substring(2) + ':' + Date.now();
    this.addSet.set(tag, element);
    return tag;
  }

  remove(element) {
    for (const [tag, el] of this.addSet.entries()) {
      if (el === element) {
        this.removeSet.add(tag);
      }
    }
  }

  read() {
    const active = new Set();
    for (const [tag, el] of this.addSet.entries()) {
      if (!this.removeSet.has(tag)) {
        active.add(el);
      }
    }
    return Array.from(active);
  }

  merge(other) {
    for (const [tag, el] of other.addSet.entries()) {
      this.addSet.set(tag, el);
    }
    for (const tag of other.removeSet) {
      this.removeSet.add(tag);
    }
  }
}

module.exports = { PNCounter, ORSet };
