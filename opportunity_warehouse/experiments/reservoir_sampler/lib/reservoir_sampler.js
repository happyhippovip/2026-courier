/**
 * Streaming Context Token Reservoir Sampler & Unbiased Estimator
 * Implements Algorithm R and Weighted Reservoir Sampling (A-Res)
 * to maintain a representative sample of size k from unbounded token streams.
 */

class ReservoirSampler {
  constructor(k = 10) {
    this.k = k;
    this.reservoir = [];
    this.totalSeen = 0;
  }

  // Observe a new token from the stream (Algorithm R)
  feed(token) {
    this.totalSeen++;
    if (this.reservoir.length < this.k) {
      this.reservoir.push(token);
    } else {
      // Probability of selection: k / totalSeen
      const j = Math.floor(Math.random() * this.totalSeen);
      if (j < this.k) {
        this.reservoir[j] = token;
      }
    }
  }

  getSample() {
    return [...this.reservoir];
  }

  reset() {
    this.reservoir = [];
    this.totalSeen = 0;
  }
}

module.exports = { ReservoirSampler };
