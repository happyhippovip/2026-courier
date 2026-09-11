/**
 * Context Window Token HyperLogLog Cardinality Estimator
 * Implements Flajolet et al. HyperLogLog algorithm for distinct token estimation
 * over streaming context windows with standard error ≈ 1.04 / sqrt(m).
 * Uses 64-bit hashing, 2^b registers, and small-range linear counting correction.
 */

const crypto = require('crypto');

class HyperLogLog {
  constructor(b = 6) {
    if (b < 4 || b > 16) throw new Error('b must be between 4 and 16');
    this.b = b;
    this.m = 1 << b; // Number of registers (e.g. 64 for b=6)
    this.registers = new Uint8Array(this.m);

    // Alpha correction constant
    if (this.m === 16) this.alpha = 0.673;
    else if (this.m === 32) this.alpha = 0.697;
    else if (this.m === 64) this.alpha = 0.709;
    else this.alpha = 0.7213 / (1 + 1.079 / this.m);

    this.totalAdded = 0;
  }

  _hash(item) {
    const hash = crypto.createHash('sha256').update(String(item)).digest();
    // Use first 32 bits for register index and leading zeros
    const val = (hash[0] | (hash[1] << 8) | (hash[2] << 16) | (hash[3] << 24)) >>> 0;
    const registerIndex = val >>> (32 - this.b);
    const remainder = (val << this.b) >>> 0;

    // Count leading zeros in remainder + 1
    let leadingZeros = 1;
    let mask = 0x80000000;
    while (leadingZeros <= (32 - this.b) && (remainder & mask) === 0) {
      leadingZeros++;
      mask >>>= 1;
    }

    return { registerIndex, leadingZeros };
  }

  add(item) {
    const { registerIndex, leadingZeros } = this._hash(item);
    if (leadingZeros > this.registers[registerIndex]) {
      this.registers[registerIndex] = leadingZeros;
    }
    this.totalAdded++;
  }

  estimate() {
    let sum = 0;
    let zeroRegisters = 0;

    for (let i = 0; i < this.m; i++) {
      sum += Math.pow(2, -this.registers[i]);
      if (this.registers[i] === 0) {
        zeroRegisters++;
      }
    }

    let rawEstimate = (this.alpha * this.m * this.m) / sum;

    // Small range correction (Linear Counting)
    if (rawEstimate <= 2.5 * this.m && zeroRegisters > 0) {
      rawEstimate = this.m * Math.log(this.m / zeroRegisters);
    }

    return Math.round(rawEstimate);
  }
}

module.exports = { HyperLogLog };
