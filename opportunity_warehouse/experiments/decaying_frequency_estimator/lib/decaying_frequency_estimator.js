/**
 * Context Window Token Decaying Frequency Estimator
 * Time-decayed streaming frequency tracker using exponential half-life decay.
 * S(t) = S(t_prev) * exp(-lambda * (t - t_prev)) + weight
 * Favors recent context tokens over historical ones with O(1) state updates.
 */

class DecayingFrequencyItem {
  constructor(key, lambda, initialTime = 0) {
    this.key = key;
    this.lambda = lambda;
    this.score = 0;
    this.lastTimestamp = initialTime;
  }

  update(timestamp, weight = 1.0) {
    const dt = Math.max(0, timestamp - this.lastTimestamp);
    // Apply decay factor e^(-lambda * dt)
    this.score = this.score * Math.exp(-this.lambda * dt) + weight;
    this.lastTimestamp = timestamp;
  }

  getScore(currentTimestamp) {
    const dt = Math.max(0, currentTimestamp - this.lastTimestamp);
    return this.score * Math.exp(-this.lambda * dt);
  }
}

class DecayingFrequencyEstimator {
  constructor(halfLifeTimeUnits = 100, maxCapacity = 256) {
    // lambda = ln(2) / halfLife
    this.lambda = Math.LN2 / halfLifeTimeUnits;
    this.maxCapacity = maxCapacity;
    this.items = new Map(); // key -> DecayingFrequencyItem
    this.currentVirtualTime = 0;
  }

  observe(key, weight = 1.0, timestamp = null) {
    if (timestamp !== null) {
      this.currentVirtualTime = Math.max(this.currentVirtualTime, timestamp);
    } else {
      this.currentVirtualTime++;
    }
    const t = this.currentVirtualTime;

    if (!this.items.has(key)) {
      if (this.items.size >= this.maxCapacity) {
        this._pruneMin(t);
      }
      this.items.set(key, new DecayingFrequencyItem(key, this.lambda, t));
    }

    const item = this.items.get(key);
    item.update(t, weight);
    return item.getScore(t);
  }

  _pruneMin(currentT) {
    let minKey = null;
    let minScore = Infinity;
    for (const [k, it] of this.items.entries()) {
      const s = it.getScore(currentT);
      if (s < minScore) {
        minScore = s;
        minKey = k;
      }
    }
    if (minKey) this.items.delete(minKey);
  }

  getScore(key, currentTimestamp = null) {
    const t = currentTimestamp !== null ? currentTimestamp : this.currentVirtualTime;
    const item = this.items.get(key);
    return item ? item.getScore(t) : 0;
  }

  getTopK(k = 5) {
    const list = [];
    const t = this.currentVirtualTime;
    for (const it of this.items.values()) {
      list.push({ key: it.key, decayedScore: it.getScore(t) });
    }
    return list.sort((a, b) => b.decayedScore - a.decayedScore).slice(0, k);
  }
}

module.exports = { DecayingFrequencyEstimator, DecayingFrequencyItem };
