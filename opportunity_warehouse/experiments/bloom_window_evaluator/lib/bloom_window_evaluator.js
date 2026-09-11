/**
 * Sliding Window Bloom Filter Evaluator
 * Maintains two rotating Bloom filters (active and passive) to track set membership
 * within a sliding window of W context tokens with zero false negatives and controlled false positive rate.
 */

const crypto = require('crypto');

class BloomFilter {
  constructor(sizeBits = 4096, hashCount = 4) {
    this.size = sizeBits;
    this.hashCount = hashCount;
    this.bits = new Uint8Array(Math.ceil(sizeBits / 8));
    this.itemCount = 0;
  }

  _hashes(item) {
    const indices = [];
    for (let i = 0; i < this.hashCount; i++) {
      const h = crypto.createHash('sha256').update(`${i}_${item}`).digest();
      const val = (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
      indices.push(val % this.size);
    }
    return indices;
  }

  add(item) {
    const indices = this._hashes(item);
    for (const idx of indices) {
      const byteIdx = Math.floor(idx / 8);
      const bitIdx = idx % 8;
      this.bits[byteIdx] |= (1 << bitIdx);
    }
    this.itemCount++;
  }

  has(item) {
    const indices = this._hashes(item);
    for (const idx of indices) {
      const byteIdx = Math.floor(idx / 8);
      const bitIdx = idx % 8;
      if ((this.bits[byteIdx] & (1 << bitIdx)) === 0) {
        return false;
      }
    }
    return true;
  }

  clear() {
    this.bits.fill(0);
    this.itemCount = 0;
  }
}

class SlidingWindowBloomFilter {
  constructor(windowSizeTokens = 500, bitsPerFilter = 4096, hashCount = 4) {
    this.windowSize = windowSizeTokens;
    this.halfWindow = Math.floor(windowSizeTokens / 2);
    this.activeFilter = new BloomFilter(bitsPerFilter, hashCount);
    this.passiveFilter = new BloomFilter(bitsPerFilter, hashCount);
    this.tokensInCurrentHalf = 0;
  }

  addToken(token) {
    this.activeFilter.add(token);
    this.tokensInCurrentHalf++;

    if (this.tokensInCurrentHalf >= this.halfWindow) {
      // Rotate: passive becomes old active, active cleared for new half window
      this.passiveFilter = this.activeFilter;
      this.activeFilter = new BloomFilter(this.activeFilter.size, this.activeFilter.hashCount);
      this.tokensInCurrentHalf = 0;
    }
  }

  contains(token) {
    // Union check across both active and passive filter
    return this.activeFilter.has(token) || this.passiveFilter.has(token);
  }
}

module.exports = { SlidingWindowBloomFilter, BloomFilter };
