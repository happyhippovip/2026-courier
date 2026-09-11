/**
 * Context Window Token MinHash Jaccard Similarity Estimator
 * Computes succinct k-dimensional MinHash signature vectors for token sets.
 * Approximates Jaccard similarity J(A, B) = |A ∩ B| / |A ∪ B| as fraction of matching sketch entries.
 */

const crypto = require('crypto');

class MinHashSketch {
  constructor(k = 64) {
    this.k = k;
    this.signature = new Uint32Array(k).fill(0xFFFFFFFF);
    // Deterministic linear hash parameters (a_i, b_i) over prime p = 2^31 - 1
    this.prime = 2147483647;
    this.a = new Uint32Array(k);
    this.b = new Uint32Array(k);
    for (let i = 0; i < k; i++) {
      this.a[i] = (i * 10007 + 12345) % this.prime;
      this.b[i] = (i * 54321 + 67890) % this.prime;
      if (this.a[i] === 0) this.a[i] = 1;
    }
    this.totalTokens = 0;
  }

  _hashToken(token) {
    const h = crypto.createHash('sha256').update(String(token)).digest();
    return (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
  }

  add(token) {
    const tokenHash = this._hashToken(token);
    for (let i = 0; i < this.k; i++) {
      // Linear congruential permutation
      const permuted = (Number(this.a[i]) * Number(tokenHash) + Number(this.b[i])) % this.prime;
      if (permuted < this.signature[i]) {
        this.signature[i] = permuted;
      }
    }
    this.totalTokens++;
  }

  addTokens(tokens) {
    for (const t of tokens) {
      this.add(t);
    }
  }

  estimateJaccard(otherSketch) {
    if (this.k !== otherSketch.k) throw new Error('Sketch dimensions must match');
    let matches = 0;
    for (let i = 0; i < this.k; i++) {
      if (this.signature[i] === otherSketch.signature[i]) {
        matches++;
      }
    }
    return matches / this.k;
  }
}

module.exports = { MinHashSketch };
