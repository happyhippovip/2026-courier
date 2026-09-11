/**
 * Context Window Token SimHash Hamming Distance Evaluator
 * Generates 64-bit locality-sensitive hashes (SimHash) for context token sequences.
 * Small differences in token composition result in small Hamming distances (<= 3 bits).
 */

const crypto = require('crypto');

class SimHash {
  constructor(bits = 64) {
    this.bits = bits;
  }

  _hashToken(token) {
    const h = crypto.createHash('sha256').update(String(token)).digest();
    // Use first 8 bytes for 64-bit integer
    return [
      (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0,
      (h[4] | (h[5] << 8) | (h[6] << 16) | (h[7] << 24)) >>> 0
    ];
  }

  computeSimHash(tokens) {
    const weights = new Int32Array(this.bits);

    for (const token of tokens) {
      const [low32, high32] = this._hashToken(token);
      for (let b = 0; b < 32; b++) {
        if ((low32 & (1 << b)) !== 0) weights[b]++;
        else weights[b]--;
      }
      for (let b = 0; b < 32; b++) {
        if ((high32 & (1 << b)) !== 0) weights[32 + b]++;
        else weights[32 + b]--;
      }
    }

    let lowFingerprint = 0;
    let highFingerprint = 0;
    for (let b = 0; b < 32; b++) {
      if (weights[b] > 0) lowFingerprint |= (1 << b);
      if (weights[32 + b] > 0) highFingerprint |= (1 << b);
    }

    return { low: lowFingerprint >>> 0, high: highFingerprint >>> 0 };
  }

  hammingDistance(fpA, fpB) {
    let diffLow = (fpA.low ^ fpB.low) >>> 0;
    let diffHigh = (fpA.high ^ fpB.high) >>> 0;

    const countBits = (n) => {
      let count = 0;
      while (n > 0) {
        count += (n & 1);
        n >>>= 1;
      }
      return count;
    };

    return countBits(diffLow) + countBits(diffHigh);
  }
}

module.exports = { SimHash };
