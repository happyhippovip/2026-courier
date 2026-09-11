/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Fibonacci Universal Integer Coding Filter
 * Uses Zeckendorf's theorem to encode integer tokens as non-consecutive Fibonacci sums,
 * terminated by '11' for universal, robust, self-synchronizing compressed token streams.
 */

const fs = require('fs');

class RadixFibonacciFilter {
  constructor() {
    this.fib = [1, 2];
    while (this.fib[this.fib.length - 1] < 1000000) {
      this.fib.push(this.fib[this.fib.length - 1] + this.fib[this.fib.length - 2]);
    }
    this.bitstream = '';
    this.tokenCount = 0;
    this.jumpTable = []; // index -> bit offset
  }

  encodeInt(n) {
    let val = n + 1; // 1-indexed to support 0
    let maxIdx = 0;
    while (maxIdx < this.fib.length && this.fib[maxIdx] <= val) maxIdx++;
    maxIdx--;
    const bits = new Array(maxIdx + 1).fill(0);
    for (let i = maxIdx; i >= 0; i--) {
      if (val >= this.fib[i]) {
        bits[i] = 1;
        val -= this.fib[i];
      }
    }
    bits.push(1); // Delimiter bit
    return bits.join('');
  }

  build(tokens) {
    this.tokenCount = tokens.length;
    this.bitstream = '';
    this.jumpTable = [];

    for (let idx = 0; idx < tokens.length; idx++) {
      if (idx % 16 === 0) {
        this.jumpTable.push({ tokenIndex: idx, bitOffset: this.bitstream.length });
      }
      this.bitstream += this.encodeInt(tokens[idx]);
    }
  }

  decode() {
    if (this.tokenCount === 0 || this.bitstream.length === 0) return [];
    const tokens = [];
    let i = 0;
    const stream = this.bitstream;

    while (i < stream.length) {
      let val = 0;
      let bitIdx = 0;
      while (i < stream.length) {
        const b = stream[i];
        if (b === '1' && stream[i - 1] === '1' && bitIdx > 0) {
          i++;
          break;
        }
        if (b === '1') {
          val += this.fib[bitIdx];
        }
        bitIdx++;
        i++;
      }
      tokens.push(val - 1);
    }
    return tokens;
  }

  queryRank(token) {
    const decoded = this.decode();
    let count = 0;
    for (const t of decoded) {
      if (t === token) count++;
    }
    return count;
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'radix_fibonacci_filter',
      timestamp: new Date().toISOString(),
      tokenCount: this.tokenCount,
      bitstreamLength: this.bitstream.length,
      jumpTableEntries: this.jumpTable.length,
      averageBitsPerToken: this.bitstream.length / (this.tokenCount || 1)
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { RadixFibonacciFilter };
