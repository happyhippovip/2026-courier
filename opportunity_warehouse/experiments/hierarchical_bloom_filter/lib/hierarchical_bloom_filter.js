/**
 * Multi-Layer Hierarchical Token Bloom Filter & Fast Negative Cache
 * Implements two-tier Bloom filter (L1 fast bitset, L2 dense bitset)
 * with zero false negatives and bounded false positive rate.
 */

class BloomFilterTier {
  constructor(size = 1024, k = 3) {
    this.size = size;
    this.k = k;
    this.bits = new Uint8Array(Math.ceil(size / 8));
  }

  hash(str, seed) {
    let h = 0x811c9dc5 ^ seed;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return Math.abs(h % this.size);
  }

  add(str) {
    for (let i = 0; i < this.k; i++) {
      const bit = this.hash(str, i * 31);
      const byteIdx = Math.floor(bit / 8);
      const bitIdx = bit % 8;
      this.bits[byteIdx] |= (1 << bitIdx);
    }
  }

  has(str) {
    for (let i = 0; i < this.k; i++) {
      const bit = this.hash(str, i * 31);
      const byteIdx = Math.floor(bit / 8);
      const bitIdx = bit % 8;
      if ((this.bits[byteIdx] & (1 << bitIdx)) === 0) {
        return false;
      }
    }
    return true;
  }
}

class HierarchicalBloomFilter {
  constructor() {
    this.l1 = new BloomFilterTier(512, 2);  // L1: Fast small filter
    this.l2 = new BloomFilterTier(4096, 4); // L2: Dense high-capacity filter
    this.itemCount = 0;
  }

  add(token) {
    this.itemCount++;
    this.l1.add(token);
    this.l2.add(token);
  }

  // Returns true if token definitely might exist, false if definitely DOES NOT exist
  mightContain(token) {
    if (!this.l1.has(token)) return false; // Early fast negative rejection
    return this.l2.has(token);
  }
}

module.exports = { HierarchicalBloomFilter, BloomFilterTier };
