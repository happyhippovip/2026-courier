/**
 * Context Window Token Bounded Roaring BitMap Index Filter
 * Implements a hybrid 32-bit Roaring Bitmap with ArrayContainer and BitsetContainer.
 * Provides high-speed set operations (intersection, union) and compact memory serialization
 * for token occurrences and positional postings lists across LLM agent context windows.
 */

const ARRAY_THRESHOLD = 4096; // Maximum size of ArrayContainer before converting to BitsetContainer

class ArrayContainer {
  constructor() {
    this.type = 'ARRAY';
    this.values = []; // sorted uint16 values
  }

  add(val) {
    const idx = this._binarySearch(val);
    if (idx >= 0) return false; // already present
    const insertIdx = -idx - 1;
    this.values.splice(insertIdx, 0, val);
    return true;
  }

  contains(val) {
    return this._binarySearch(val) >= 0;
  }

  cardinality() {
    return this.values.length;
  }

  _binarySearch(target) {
    let low = 0;
    let high = this.values.length - 1;
    while (low <= high) {
      const mid = (low + high) >>> 1;
      const midVal = this.values[mid];
      if (midVal < target) {
        low = mid + 1;
      } else if (midVal > target) {
        high = mid - 1;
      } else {
        return mid;
      }
    }
    return -(low + 1);
  }

  toBitsetContainer() {
    const bitset = new BitsetContainer();
    for (let i = 0; i < this.values.length; i++) {
      bitset.add(this.values[i]);
    }
    return bitset;
  }

  getByteSize() {
    return this.values.length * 2; // 2 bytes per uint16
  }
}

class BitsetContainer {
  constructor() {
    this.type = 'BITSET';
    // 65536 bits represented as 2048 32-bit integers
    this.words = new Uint32Array(2048);
    this._cardinality = 0;
  }

  add(val) {
    const wordIdx = val >>> 5;
    const bitMask = 1 << (val & 31);
    if ((this.words[wordIdx] & bitMask) === 0) {
      this.words[wordIdx] |= bitMask;
      this._cardinality++;
      return true;
    }
    return false;
  }

  contains(val) {
    const wordIdx = val >>> 5;
    const bitMask = 1 << (val & 31);
    return (this.words[wordIdx] & bitMask) !== 0;
  }

  cardinality() {
    return this._cardinality;
  }

  getByteSize() {
    return 2048 * 4; // 8192 bytes
  }
}

class RoaringBitmap {
  constructor() {
    // Map chunkKey (upper 16 bits) -> Container
    this.chunks = new Map();
  }

  add(val) {
    if (typeof val !== 'number' || val < 0 || val > 0xFFFFFFFF) return false;
    const chunkKey = val >>> 16;
    const lowerVal = val & 0xFFFF;

    let container = this.chunks.get(chunkKey);
    if (!container) {
      container = new ArrayContainer();
      this.chunks.set(chunkKey, container);
    }

    const added = container.add(lowerVal);
    if (added && container.type === 'ARRAY' && container.cardinality() > ARRAY_THRESHOLD) {
      this.chunks.set(chunkKey, container.toBitsetContainer());
    }
    return added;
  }

  contains(val) {
    if (typeof val !== 'number' || val < 0 || val > 0xFFFFFFFF) return false;
    const chunkKey = val >>> 16;
    const lowerVal = val & 0xFFFF;
    const container = this.chunks.get(chunkKey);
    if (!container) return false;
    return container.contains(lowerVal);
  }

  cardinality() {
    let total = 0;
    for (const container of this.chunks.values()) {
      total += container.cardinality();
    }
    return total;
  }

  and(other) {
    const result = new RoaringBitmap();
    for (const [chunkKey, c1] of this.chunks.entries()) {
      const c2 = other.chunks.get(chunkKey);
      if (!c2) continue;

      if (c1.type === 'ARRAY') {
        for (const v of c1.values) {
          if (c2.contains(v)) {
            result.add((chunkKey << 16) | v);
          }
        }
      } else if (c2.type === 'ARRAY') {
        for (const v of c2.values) {
          if (c1.contains(v)) {
            result.add((chunkKey << 16) | v);
          }
        }
      } else {
        // Both BITSET
        for (let word = 0; word < 2048; word++) {
          const common = c1.words[word] & c2.words[word];
          if (common !== 0) {
            for (let bit = 0; bit < 32; bit++) {
              if ((common & (1 << bit)) !== 0) {
                result.add((chunkKey << 16) | (word * 32 + bit));
              }
            }
          }
        }
      }
    }
    return result;
  }

  or(other) {
    const result = new RoaringBitmap();
    for (const [chunkKey, c] of this.chunks.entries()) {
      if (c.type === 'ARRAY') {
        for (const v of c.values) result.add((chunkKey << 16) | v);
      } else {
        for (let w = 0; w < 2048; w++) {
          const word = c.words[w];
          if (word !== 0) {
            for (let b = 0; b < 32; b++) {
              if ((word & (1 << b)) !== 0) result.add((chunkKey << 16) | (w * 32 + b));
            }
          }
        }
      }
    }
    for (const [chunkKey, c] of other.chunks.entries()) {
      if (c.type === 'ARRAY') {
        for (const v of c.values) result.add((chunkKey << 16) | v);
      } else {
        for (let w = 0; w < 2048; w++) {
          const word = c.words[w];
          if (word !== 0) {
            for (let b = 0; b < 32; b++) {
              if ((word & (1 << b)) !== 0) result.add((chunkKey << 16) | (w * 32 + b));
            }
          }
        }
      }
    }
    return result;
  }

  getMetrics() {
    let roaringBytes = 0;
    const chunkSummary = [];
    for (const [key, c] of this.chunks.entries()) {
      const b = c.getByteSize() + 4; // 4 bytes for chunk header/key
      roaringBytes += b;
      chunkSummary.push({ chunkKey: key, type: c.type, cardinality: c.cardinality(), bytes: b });
    }

    const totalElements = this.cardinality();
    const rawArrayBytes = totalElements * 4; // 4 bytes per 32-bit int in flat array
    const savingsPercent = rawArrayBytes > 0 
      ? ((1 - (roaringBytes / rawArrayBytes)) * 100).toFixed(2) + '%'
      : '0.00%';

    return {
      chunkCount: this.chunks.size,
      totalElements,
      roaringBytes,
      rawArrayBytes,
      savingsPercent,
      chunks: chunkSummary
    };
  }
}

module.exports = { RoaringBitmap, ArrayContainer, BitsetContainer };
