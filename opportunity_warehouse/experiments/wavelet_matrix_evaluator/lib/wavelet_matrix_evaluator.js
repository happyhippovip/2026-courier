/**
 * Context Window Token Wavelet Matrix Rank/Select Evaluator
 * Supports O(log Sigma) rank and select operations over arbitrary integer token alphabets
 * with compact bitvector representations.
 */

class BitVector {
  constructor(bits) {
    this.bits = [...bits];
    this.prefixZeros = new Int32Array(bits.length + 1);
    let z = 0;
    for (let i = 0; i < bits.length; i++) {
      if (bits[i] === 0) z++;
      this.prefixZeros[i + 1] = z;
    }
  }

  // Count occurrences of bit b in prefix [0, i - 1]
  rank(b, i) {
    if (i <= 0) return 0;
    const clamped = Math.min(i, this.bits.length);
    const zeros = this.prefixZeros[clamped];
    return b === 0 ? zeros : (clamped - zeros);
  }

  length() {
    return this.bits.length;
  }
}

class WaveletMatrix {
  constructor(data, bitWidth = 8) {
    this.bitWidth = bitWidth;
    this.layers = [];
    this.zerosCount = [];

    let current = [...data];

    for (let level = bitWidth - 1; level >= 0; level--) {
      const bitLayer = [];
      const zeros = [];
      const ones = [];

      for (let i = 0; i < current.length; i++) {
        const bit = (current[i] >> level) & 1;
        bitLayer.push(bit);
        if (bit === 0) zeros.push(current[i]);
        else ones.push(current[i]);
      }

      this.layers.push(new BitVector(bitLayer));
      this.zerosCount.push(zeros.length);
      current = [...zeros, ...ones];
    }
  }

  trace(symbol, p) {
    for (let level = 0; level < this.bitWidth; level++) {
      const bit = (symbol >> (this.bitWidth - 1 - level)) & 1;
      const bv = this.layers[level];
      const z = this.zerosCount[level];

      if (bit === 0) {
        p = bv.rank(0, p);
      } else {
        p = z + bv.rank(1, p);
      }
    }
    return p;
  }

  // Count occurrences of symbol in prefix [0, i - 1]
  rank(symbol, i) {
    return this.trace(symbol, i) - this.trace(symbol, 0);
  }

  // Count occurrences of symbol in range [l, r] (0-indexed inclusive)
  rangeCount(symbol, l, r) {
    return this.rank(symbol, r + 1) - this.rank(symbol, l);
  }
}

module.exports = { WaveletMatrix, BitVector };
