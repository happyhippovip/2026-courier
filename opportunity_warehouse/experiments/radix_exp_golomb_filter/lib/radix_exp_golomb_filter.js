/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Exponential-Golomb Bitvector Filter
 * Variable-length Exponential-Golomb coding (k-th order) for geometrically distributed
 * tokens in context windows, coupled with a radix jump table for fast random access.
 */

const fs = require('fs');

class RadixExpGolombFilter {
  constructor(defaultOrderK = 0) {
    this.orderK = defaultOrderK;
    this.bitstream = '';
    this.tokenCount = 0;
    this.jumpTable = []; // tokenIndex -> bitOffset
  }

  encodeExpGolomb(x, k) {
    const y = x + (1 << k);
    const m = Math.floor(Math.log2(y));
    const prefixZeros = m - k;
    const suffix = y.toString(2);
    return '0'.repeat(prefixZeros) + suffix;
  }

  build(tokens, k = this.orderK) {
    this.orderK = k;
    this.tokenCount = tokens.length;
    this.bitstream = '';
    this.jumpTable = [];

    for (let i = 0; i < tokens.length; i++) {
      if (i % 16 === 0) {
        this.jumpTable.push({ tokenIndex: i, bitOffset: this.bitstream.length });
      }
      this.bitstream += this.encodeExpGolomb(tokens[i], this.orderK);
    }
  }

  decode(k = this.orderK) {
    if (this.tokenCount === 0 || this.bitstream.length === 0) return [];
    const results = [];
    let i = 0;
    const stream = this.bitstream;

    while (i < stream.length) {
      let zeros = 0;
      while (i < stream.length && stream[i] === '0') {
        zeros++;
        i++;
      }
      if (i >= stream.length) break;
      const m = zeros + k;
      const binStr = stream.substring(i, i + m + 1);
      i += m + 1;
      const y = parseInt(binStr, 2);
      const x = y - (1 << k);
      results.push(x);
    }
    return results;
  }

  queryCount(token) {
    const decoded = this.decode();
    let count = 0;
    for (const t of decoded) {
      if (t === token) count++;
    }
    return count;
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'radix_exp_golomb_filter',
      timestamp: new Date().toISOString(),
      orderK: this.orderK,
      tokenCount: this.tokenCount,
      bitstreamLength: this.bitstream.length,
      averageBitsPerToken: this.bitstream.length / (this.tokenCount || 1)
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { RadixExpGolombFilter };
