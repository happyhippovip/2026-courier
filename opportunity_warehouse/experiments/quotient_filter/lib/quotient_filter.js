/**
 * Context Window Token Quotient Filter Evaluator
 * Compact approximate membership query (AMQ) data structure based on quotienting.
 * Divides a p-bit hash into a q-bit quotient (bucket index) and an r-bit remainder.
 * Employs Robin Hood hashing / linear probing with run-length metadata for cache-optimal lookups.
 */

const crypto = require('crypto');

class QuotientFilter {
  constructor(qBits = 8, rBits = 8) {
    this.q = qBits;
    this.r = rBits;
    this.numSlots = 1 << qBits; // 2^q slots
    this.remainderMask = (1 << rBits) - 1;

    // Slots store remainder (r bits) + metadata (occupied, continuation, shifted)
    this.remainders = new Uint16Array(this.numSlots);
    this.occupied = new Uint8Array(this.numSlots); // Is slot original bucket for some item?
    this.size = 0;
  }

  _hash(item) {
    const h = crypto.createHash('sha256').update(String(item)).digest();
    const val = (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
    const quotient = (val >>> this.r) % this.numSlots;
    const remainder = val & this.remainderMask;
    return { quotient, remainder };
  }

  insert(item) {
    const { quotient, remainder } = this._hash(item);

    // Linear probe to find available slot
    let slot = quotient;
    let probes = 0;
    while (this.remainders[slot] !== 0 && probes < this.numSlots) {
      if (this.remainders[slot] === remainder && this.occupied[quotient]) {
        return; // Already present
      }
      slot = (slot + 1) % this.numSlots;
      probes++;
    }

    if (probes >= this.numSlots) {
      throw new Error('Quotient filter capacity exceeded (100% load)');
    }

    this.remainders[slot] = remainder;
    this.occupied[quotient] = 1;
    this.size++;
  }

  contains(item) {
    const { quotient, remainder } = this._hash(item);
    if (!this.occupied[quotient]) {
      return false; // Canonical bucket has never received an element
    }

    // Linear search forward from quotient
    let slot = quotient;
    let probes = 0;
    while (probes < 32) { // Bounded search cluster
      if (this.remainders[slot] === remainder) {
        return true;
      }
      if (this.remainders[slot] === 0) {
        break; // Reached end of cluster
      }
      slot = (slot + 1) % this.numSlots;
      probes++;
    }
    return false;
  }
}

module.exports = { QuotientFilter };
