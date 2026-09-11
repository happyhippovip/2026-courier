/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Golomb Power-of-Two Filter
 * Implements Golomb coding parameterized for powers of two M = 2^k, with unary quotient and binary remainder.
 */

class RadixGolombPotFilter {
  constructor(k = 3) {
    this.k = k;
    this.mask = (1 << k) - 1;
    this.bitstream = '';
    this.tokenCount = 0;
  }

  encode(val) {
    if (val < 0) val = 0;
    const q = val >> this.k;
    const r = val & this.mask;
    const unary = '0'.repeat(q) + '1';
    const binary = r.toString(2).padStart(this.k, '0');
    return unary + binary;
  }

  decode(bitstr) {
    const results = [];
    let pos = 0;
    while (pos < bitstr.length) {
      let q = 0;
      while (pos < bitstr.length && bitstr[pos] === '0') {
        q++;
        pos++;
      }
      if (pos >= bitstr.length) break;
      pos++; // skip '1'

      if (pos + this.k > bitstr.length) break;
      const binSlice = bitstr.substring(pos, pos + this.k);
      pos += this.k;
      const r = parseInt(binSlice, 2);
      const val = (q << this.k) | r;
      results.push(val);
    }
    return results;
  }

  build(tokens) {
    this.tokenCount = tokens.length;
    this.bitstream = '';
    for (const t of tokens) {
      const val = typeof t === 'number' ? t : (t.id || 0);
      this.bitstream += this.encode(val);
    }
  }
}

module.exports = { RadixGolombPotFilter };
