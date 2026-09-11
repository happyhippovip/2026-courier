/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Elias-Omega Universal Bitvector Filter
 * Implements Elias-Omega recursive prefix coding terminated by a '0' bit.
 */

class RadixEliasOmegaFilter {
  constructor() {
    this.bitstream = '';
    this.tokenCount = 0;
  }

  encodeOmega(n) {
    if (n <= 0) n = 1;
    if (n === 1) return '0';

    let s = '0';
    let k = n;
    while (k > 1) {
      const bin = k.toString(2);
      s = bin + s;
      k = bin.length - 1;
    }
    return s;
  }

  decodeOmega(bitstr) {
    const results = [];
    let pos = 0;
    while (pos < bitstr.length) {
      let n = 1;
      while (pos < bitstr.length && bitstr[pos] === '1') {
        const len = n + 1;
        const binSlice = bitstr.substring(pos, pos + len);
        pos += len;
        n = parseInt(binSlice, 2);
      }
      if (pos < bitstr.length && bitstr[pos] === '0') {
        pos++; // skip terminating 0
        results.push(n);
      }
    }
    return results;
  }

  build(tokens) {
    this.tokenCount = tokens.length;
    this.bitstream = '';
    for (const t of tokens) {
      const val = typeof t === 'number' ? t : (t.id || 1);
      this.bitstream += this.encodeOmega(val);
    }
  }
}

module.exports = { RadixEliasOmegaFilter };
