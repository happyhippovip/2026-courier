/**
 * Context Window Sliding-Window Quantized Bloom Filter
 * Sub-kilobyte bitset filter for O(1) set-membership queries across large context histories,
 * preventing duplicate tool invocations and verifying observation novelty with near-zero memory footprint.
 */

const crypto = require('crypto');

class QuantizedBloomFilter {
  constructor(sizeBits = 1024, numHashes = 3) {
    this.sizeBits = sizeBits;
    this.numHashes = numHashes;
    this.bitset = new Uint8Array(Math.ceil(sizeBits / 8));
    this.itemCount = 0;
  }

  getHashes(item) {
    const hashes = [];
    for (let i = 0; i < this.numHashes; i++) {
      const h = crypto.createHash('sha256')
        .update(item + ':' + i)
        .digest();
      // Read 32-bit uint and modulo sizeBits
      const val = h.readUInt32BE(0);
      hashes.push(val % this.sizeBits);
    }
    return hashes;
  }

  add(item) {
    if (!item) return;
    const bitPositions = this.getHashes(String(item));
    for (const pos of bitPositions) {
      const byteIndex = Math.floor(pos / 8);
      const bitOffset = pos % 8;
      this.bitset[byteIndex] |= (1 << bitOffset);
    }
    this.itemCount += 1;
  }

  has(item) {
    if (!item) return false;
    const bitPositions = this.getHashes(String(item));
    for (const pos of bitPositions) {
      const byteIndex = Math.floor(pos / 8);
      const bitOffset = pos % 8;
      if ((this.bitset[byteIndex] & (1 << bitOffset)) === 0) {
        return false; // Definitely not present
      }
    }
    return true; // Probably present
  }

  estimateFalsePositiveProbability() {
    // p = (1 - e^(-kn/m))^k
    const exponent = -(this.numHashes * this.itemCount) / this.sizeBits;
    const p = Math.pow(1 - Math.exp(exponent), this.numHashes);
    return Number(p.toFixed(5));
  }

  reset() {
    this.bitset.fill(0);
    this.itemCount = 0;
  }
}

module.exports = { QuantizedBloomFilter };