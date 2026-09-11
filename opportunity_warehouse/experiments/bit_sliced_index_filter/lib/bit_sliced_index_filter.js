/**
 * Context Window Token Dynamic Bounded Fast Succinct Bit-Sliced Index (BSI) Filter
 * Represents multi-bit integer attributes (saliency scores, frequency counts, attention ranks)
 * as bit slices for lightning-fast SIMD-style bitwise range filtering and aggregation.
 */

class BitSlicedIndex {
  constructor(bitWidth = 8, capacity = 1024) {
    this.bitWidth = bitWidth;
    this.capacity = capacity;
    this.length = 0;
    // slices[b] is Uint32Array holding the b-th bit of each element
    this.wordsCount = Math.ceil(capacity / 32);
    this.slices = [];
    for (let b = 0; b < bitWidth; b++) {
      this.slices.push(new Uint32Array(this.wordsCount));
    }
  }

  append(val) {
    if (this.length >= this.capacity) {
      this._grow();
    }
    const idx = this.length;
    const wordIdx = idx >>> 5;
    const bitMask = 1 << (idx & 31);

    const clampedVal = Math.max(0, Math.min((1 << this.bitWidth) - 1, val));
    for (let b = 0; b < this.bitWidth; b++) {
      if ((clampedVal & (1 << b)) !== 0) {
        this.slices[b][wordIdx] |= bitMask;
      }
    }
    this.length++;
    return idx;
  }

  _grow() {
    const newCap = this.capacity * 2;
    const newWords = Math.ceil(newCap / 32);
    for (let b = 0; b < this.bitWidth; b++) {
      const newSlice = new Uint32Array(newWords);
      newSlice.set(this.slices[b]);
      this.slices[b] = newSlice;
    }
    this.capacity = newCap;
    this.wordsCount = newWords;
  }

  getValue(idx) {
    if (idx < 0 || idx >= this.length) return null;
    const wordIdx = idx >>> 5;
    const bitMask = 1 << (idx & 31);
    let val = 0;
    for (let b = 0; b < this.bitWidth; b++) {
      if ((this.slices[b][wordIdx] & bitMask) !== 0) {
        val |= (1 << b);
      }
    }
    return val;
  }

  filterGreaterThan(threshold) {
    // Returns array of indices where value > threshold using BSI bitwise evaluation
    const G = new Uint32Array(this.wordsCount);
    const E = new Uint32Array(this.wordsCount);
    E.fill(0xFFFFFFFF);

    for (let b = this.bitWidth - 1; b >= 0; b--) {
      const tb = (threshold >>> b) & 1;
      const Sb = this.slices[b];

      if (tb === 0) {
        for (let w = 0; w < this.wordsCount; w++) {
          G[w] |= (E[w] & Sb[w]);
          E[w] &= (~Sb[w]);
        }
      } else {
        for (let w = 0; w < this.wordsCount; w++) {
          E[w] &= Sb[w];
        }
      }
    }

    return this._bitmapToIndices(G);
  }

  filterRange(minVal, maxVal) {
    // Range query: minVal <= x <= maxVal
    const indices = [];
    for (let i = 0; i < this.length; i++) {
      const v = this.getValue(i);
      if (v >= minVal && v <= maxVal) {
        indices.push(i);
      }
    }
    return indices;
  }

  sum() {
    // Exact sum computation using popcounts of bit slices
    let total = 0;
    for (let b = 0; b < this.bitWidth; b++) {
      let slicePopcount = 0;
      for (let w = 0; w < this.wordsCount; w++) {
        let word = this.slices[b][w];
        // clear unused trailing bits in last word
        if (w === this.wordsCount - 1) {
          const remainingBits = this.length & 31;
          if (remainingBits > 0) {
            const mask = (1 << remainingBits) - 1;
            word &= mask;
          }
        }
        slicePopcount += this._popcount32(word);
      }
      total += slicePopcount * (1 << b);
    }
    return total;
  }

  _popcount32(x) {
    x = x - ((x >>> 1) & 0x55555555);
    x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
    return (((x + (x >>> 4)) & 0x0F0F0F0F) * 0x01010101) >>> 24;
  }

  _bitmapToIndices(bitmap) {
    const indices = [];
    for (let i = 0; i < this.length; i++) {
      const wordIdx = i >>> 5;
      const bitMask = 1 << (i & 31);
      if ((bitmap[wordIdx] & bitMask) !== 0) {
        indices.push(i);
      }
    }
    return indices;
  }

  getMetrics() {
    const bsiBytes = this.bitWidth * this.wordsCount * 4;
    const rawArrayBytes = this.length * 4;
    const compressionRatio = rawArrayBytes > 0 
      ? (1 - (bsiBytes / rawArrayBytes)).toFixed(4)
      : '0.0000';

    return {
      bitWidth: this.bitWidth,
      elementCount: this.length,
      bsiBytes,
      rawArrayBytes,
      compressionRatio: parseFloat(compressionRatio),
      savingsPercent: (parseFloat(compressionRatio) * 100).toFixed(2) + '%'
    };
  }
}

module.exports = { BitSlicedIndex };
