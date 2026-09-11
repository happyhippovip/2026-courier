/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Rice Integer Coding Filter
 * Implements Golomb-Rice variable-length coding with parameter M = 2^k, splitting integers
 * into unary quotient and binary remainder, with radix jump table acceleration.
 */

const fs = require('fs');

class RadixRiceFilter {
  constructor(defaultK = 2) {
    this.k = defaultK;
    this.bitstream = '';
    this.tokenCount = 0;
    this.jumpTable = []; // tokenIndex -> bitOffset
  }

  encodeRice(x, k) {
    const q = x >> k;
    const r = x & ((1 << k) - 1);
    const unary = '0'.repeat(q) + '1';
    const binary = k > 0 ? r.toString(2).padStart(k, '0') : '';
    return unary + binary;
  }

  build(tokens, k = this.k) {
    this.k = k;
    this.tokenCount = tokens.length;
    this.bitstream = '';
    this.jumpTable = [];

    for (let i = 0; i < tokens.length; i++) {
      if (i % 16 === 0) {
        this.jumpTable.push({ tokenIndex: i, bitOffset: this.bitstream.length });
      }
      this.bitstream += this.encodeRice(tokens[i], this.k);
    }
  }

  decode(k = this.k) {
    if (this.tokenCount === 0 || this.bitstream.length === 0) return [];
    const results = [];
    let i = 0;
    const stream = this.bitstream;

    while (i < stream.length) {
      let q = 0;
      while (i < stream.length && stream[i] === '0') {
        q++;
        i++;
      }
      if (i >= stream.length) break;
      i++; // consume '1' delimiter

      let r = 0;
      if (k > 0) {
        if (i + k > stream.length) break;
        const binStr = stream.substring(i, i + k);
        i += k;
        r = parseInt(binStr, 2);
      }
      const x = (q << k) + r;
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
      subsystem: 'radix_rice_filter',
      timestamp: new Date().toISOString(),
      paramK: this.k,
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

module.exports = { RadixRiceFilter };
