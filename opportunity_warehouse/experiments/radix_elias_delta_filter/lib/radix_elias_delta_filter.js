/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Elias-Delta Universal Bitvector Filter
 * Encodes integers using Elias-Delta coding: encodes (1 + floor(log2(n))) via Elias-Gamma, followed by lower order bits of n.
 */

class RadixEliasDeltaFilter {
  constructor() {
    this.bitstream = '';
    this.tokenCount = 0;
  }

  encodeGamma(n) {
    if (n <= 0) n = 1;
    const len = Math.floor(Math.log2(n));
    const unary = '0'.repeat(len);
    const binary = n.toString(2);
    return unary + binary;
  }

  encodeDelta(n) {
    if (n <= 0) n = 1;
    const len = Math.floor(Math.log2(n));
    const gammaPart = this.encodeGamma(len + 1);
    const remBits = n.toString(2).substring(1);
    return gammaPart + remBits;
  }

  decodeDelta(bitstr) {
    const results = [];
    let pos = 0;
    while (pos < bitstr.length) {
      let zeros = 0;
      while (pos < bitstr.length && bitstr[pos] === '0') {
        zeros++;
        pos++;
      }
      if (pos >= bitstr.length) break;
      // Read gamma value
      const gammaLen = zeros + 1;
      const gammaStr = bitstr.substring(pos, pos + gammaLen);
      pos += gammaLen;
      const L = parseInt(gammaStr, 2);

      const remLen = L - 1;
      if (remLen === 0) {
        results.push(1);
      } else {
        const remStr = bitstr.substring(pos, pos + remLen);
        pos += remLen;
        const val = parseInt('1' + remStr, 2);
        results.push(val);
      }
    }
    return results;
  }

  build(tokens) {
    this.tokenCount = tokens.length;
    this.bitstream = '';
    for (const t of tokens) {
      const val = typeof t === 'number' ? t : (t.id || 1);
      this.bitstream += this.encodeDelta(val);
    }
  }
}

module.exports = { RadixEliasDeltaFilter };
