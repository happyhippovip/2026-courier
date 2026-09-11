/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Roaring Bit-Vector Indexer
 * Implements dual-container Roaring Bitmap partition (Array Container for sparse < 4096 elements,
 * Bitset Container for dense >= 4096 elements per 16-bit bucket).
 */

class RoaringContainer {
  constructor(key) {
    this.key = key; // 16-bit high key
    this.isArray = true;
    this.array = []; // sorted 16-bit integers
    this.bitmap = null; // Buffer of 8192 bytes (65536 bits)
    this.cardinality = 0;
  }

  add(lowVal) {
    if (this.isArray) {
      if (!this.array.includes(lowVal)) {
        this.array.push(lowVal);
        this.array.sort((a, b) => a - b);
        this.cardinality++;
        if (this.cardinality >= 4096) {
          this.convertToBitmap();
        }
      }
    } else {
      const byteIdx = Math.floor(lowVal / 8);
      const bitOffset = lowVal % 8;
      if ((this.bitmap[byteIdx] & (1 << bitOffset)) === 0) {
        this.bitmap[byteIdx] |= (1 << bitOffset);
        this.cardinality++;
      }
    }
  }

  contains(lowVal) {
    if (this.isArray) {
      return this.array.includes(lowVal);
    } else {
      const byteIdx = Math.floor(lowVal / 8);
      const bitOffset = lowVal % 8;
      return (this.bitmap[byteIdx] & (1 << bitOffset)) !== 0;
    }
  }

  convertToBitmap() {
    this.isArray = false;
    this.bitmap = Buffer.alloc(8192);
    for (const val of this.array) {
      const byteIdx = Math.floor(val / 8);
      const bitOffset = val % 8;
      this.bitmap[byteIdx] |= (1 << bitOffset);
    }
    this.array = [];
  }
}

class RadixRoaringBitVectorIndexer {
  constructor() {
    this.containers = new Map(); // highKey -> RoaringContainer
  }

  add(val) {
    if (val < 0 || val > 0xFFFFFFFF) return;
    const highKey = Math.floor(val / 65536);
    const lowVal = val % 65536;

    if (!this.containers.has(highKey)) {
      this.containers.set(highKey, new RoaringContainer(highKey));
    }
    this.containers.get(highKey).add(lowVal);
  }

  contains(val) {
    if (val < 0 || val > 0xFFFFFFFF) return false;
    const highKey = Math.floor(val / 65536);
    const lowVal = val % 65536;

    if (!this.containers.has(highKey)) return false;
    return this.containers.get(highKey).contains(lowVal);
  }

  getCardinality() {
    let sum = 0;
    for (const c of this.containers.values()) {
      sum += c.cardinality;
    }
    return sum;
  }

  getContainerStats() {
    let arrayContainers = 0;
    let bitmapContainers = 0;
    for (const c of this.containers.values()) {
      if (c.isArray) arrayContainers++;
      else bitmapContainers++;
    }
    return {
      totalContainers: this.containers.size,
      arrayContainers: arrayContainers,
      bitmapContainers: bitmapContainers,
      totalCardinality: this.getCardinality()
    };
  }
}

module.exports = { RadixRoaringBitVectorIndexer };
