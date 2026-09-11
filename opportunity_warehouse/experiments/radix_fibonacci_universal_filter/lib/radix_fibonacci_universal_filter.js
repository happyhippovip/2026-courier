/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Fibonacci Universal Coding Filter
 * Implements Zeckendorf Fibonacci integer representation with '11' delimiter for self-synchronizing token streams.
 */

class RadixFibonacciUniversalFilter {
  constructor() {
    this.fibs = [1, 2];
    while (this.fibs[this.fibs.length - 1] < 100000) {
      const len = this.fibs.length;
      this.fibs.push(this.fibs[len - 1] + this.fibs[len - 2]);
    }
    this.bitstream = '';
    this.tokenCount = 0;
  }

  encodeInteger(n) {
    if (n <= 0) n = 1;
    let maxIdx = 0;
    while (maxIdx < this.fibs.length && this.fibs[maxIdx] <= n) {
      maxIdx++;
    }
    maxIdx--;

    const bits = new Array(maxIdx + 1).fill('0');
    let rem = n;
    for (let i = maxIdx; i >= 0; i--) {
      if (rem >= this.fibs[i]) {
        bits[i] = '1';
        rem -= this.fibs[i];
      }
    }
    // Fibonacci code appends extra '1' bit as self-synchronizing delimiter
    return bits.join('') + '1';
  }

  decodeStream(bitstr) {
    const results = [];
    let currBits = '';
    for (let i = 0; i < bitstr.length; i++) {
      currBits += bitstr[i];
      if (currBits.endsWith('11') && currBits.length >= 2) {
        // Decode Fibonacci codeword
        const code = currBits.slice(0, -1); // remove trailing delimiter '1'
        let sum = 0;
        for (let j = 0; j < code.length; j++) {
          if (code[j] === '1') {
            sum += this.fibs[j];
          }
        }
        results.push(sum);
        currBits = '';
      }
    }
    return results;
  }

  build(tokens) {
    this.tokenCount = tokens.length;
    this.bitstream = '';
    for (const t of tokens) {
      this.bitstream += this.encodeInteger(t.id || t);
    }
  }
}

module.exports = { RadixFibonacciUniversalFilter };
