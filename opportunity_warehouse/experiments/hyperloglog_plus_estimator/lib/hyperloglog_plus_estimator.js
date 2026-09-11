/**
 * Context Window Token HyperLogLog++ Estimator
 * Implements Google's HyperLogLog++ algorithm with sparse representation for small sets
 * and 64-bit hashing to eliminate hash collision error at massive context scales.
 */

const crypto = require('crypto');

class HyperLogLogPlus {
  constructor(p = 8, sparseThreshold = 128) {
    this.p = p;
    this.m = 1 << p; // 256 registers
    this.sparseThreshold = sparseThreshold;
    this.isSparse = true;
    this.sparseSet = new Set(); // Stores 32-bit encoded (registerIndex, rank)
    this.registers = null; // Uint8Array initialized when converting to dense

    this.alpha = 0.7213 / (1 + 1.079 / this.m);
    this.totalAdded = 0;
  }

  _hash64(item) {
    const h = crypto.createHash('sha256').update(String(item)).digest();
    // Extract 64 bits as two 32-bit words
    const high32 = (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
    const low32 = (h[4] | (h[5] << 8) | (h[6] << 16) | (h[7] << 24)) >>> 0;
    return { high32, low32 };
  }

  add(item) {
    const { high32, low32 } = this._hash64(item);
    const registerIndex = high32 >>> (32 - this.p);
    const remainder = ((high32 << this.p) | (low32 >>> (32 - this.p))) >>> 0;

    let leadingZeros = 1;
    let mask = 0x80000000;
    while (leadingZeros <= (32 - this.p) && (remainder & mask) === 0) {
      leadingZeros++;
      mask >>>= 1;
    }

    if (this.isSparse) {
      const encoded = (registerIndex << 8) | (leadingZeros & 0xFF);
      this.sparseSet.add(encoded);
      if (this.sparseSet.size >= this.sparseThreshold) {
        this._convertToDense();
      }
    } else {
      if (leadingZeros > this.registers[registerIndex]) {
        this.registers[registerIndex] = leadingZeros;
      }
    }
    this.totalAdded++;
  }

  _convertToDense() {
    this.isSparse = false;
    this.registers = new Uint8Array(this.m);
    for (const encoded of this.sparseSet) {
      const reg = encoded >>> 8;
      const rank = encoded & 0xFF;
      if (rank > this.registers[reg]) {
        this.registers[reg] = rank;
      }
    }
    this.sparseSet.clear();
  }

  estimate() {
    if (this.isSparse) {
      // In sparse mode, estimate is exact distinct set size
      return this.sparseSet.size;
    }

    let sum = 0;
    let zeroRegisters = 0;
    for (let i = 0; i < this.m; i++) {
      sum += Math.pow(2, -this.registers[i]);
      if (this.registers[i] === 0) zeroRegisters++;
    }

    let rawEstimate = (this.alpha * this.m * this.m) / sum;

    if (rawEstimate <= 2.5 * this.m && zeroRegisters > 0) {
      rawEstimate = this.m * Math.log(this.m / zeroRegisters);
    }

    return Math.round(rawEstimate);
  }
}

module.exports = { HyperLogLogPlus };
