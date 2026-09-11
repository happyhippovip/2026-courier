/**
 * Context Window Token Roaring Bitmap Compressor
 * Hybrid container compressed bitmap (Array Container for sparse < 4096 elements,
 * Bitset Container for dense >= 4096 elements) with ultra-fast set operations.
 */

class RoaringBitmap {
  constructor() {
    this.containers = new Map(); // chunkIndex (upper 16 bits) -> { type: 'ARRAY' | 'BITSET', data }
    this.cardinality = 0;
  }

  add(val) {
    const chunk = val >>> 16;
    const offset = val & 0xFFFF;

    if (!this.containers.has(chunk)) {
      this.containers.set(chunk, { type: 'ARRAY', data: [offset] });
      this.cardinality++;
      return;
    }

    const container = this.containers.get(chunk);
    if (container.type === 'ARRAY') {
      const idx = container.data.indexOf(offset);
      if (idx === -1) {
        container.data.push(offset);
        container.data.sort((a, b) => a - b);
        this.cardinality++;

        // Convert to BITSET if threshold reached
        if (container.data.length >= 4096) {
          const bitset = new Uint8Array(8192); // 65536 bits = 8192 bytes
          for (const pos of container.data) {
            bitset[pos >>> 3] |= (1 << (pos & 7));
          }
          container.type = 'BITSET';
          container.data = bitset;
        }
      }
    } else {
      // BITSET
      const byteIdx = offset >>> 3;
      const bitIdx = offset & 7;
      if ((container.data[byteIdx] & (1 << bitIdx)) === 0) {
        container.data[byteIdx] |= (1 << bitIdx);
        this.cardinality++;
      }
    }
  }

  has(val) {
    const chunk = val >>> 16;
    const offset = val & 0xFFFF;
    const container = this.containers.get(chunk);
    if (!container) return false;

    if (container.type === 'ARRAY') {
      return container.data.includes(offset);
    } else {
      const byteIdx = offset >>> 3;
      const bitIdx = offset & 7;
      return (container.data[byteIdx] & (1 << bitIdx)) !== 0;
    }
  }

  // Intersect with another Roaring Bitmap
  intersect(other) {
    const result = new RoaringBitmap();
    for (const [chunk, c1] of this.containers.entries()) {
      if (other.containers.has(chunk)) {
        const c2 = other.containers.get(chunk);
        // Fast intersection
        if (c1.type === 'ARRAY' && c2.type === 'ARRAY') {
          for (const val of c1.data) {
            if (c2.data.includes(val)) {
              result.add((chunk << 16) | val);
            }
          }
        } else {
          // Fallback universal iteration
          for (let offset = 0; offset < 65536; offset++) {
            const v = (chunk << 16) | offset;
            if (this.has(v) && other.has(v)) {
              result.add(v);
            }
          }
        }
      }
    }
    return result;
  }
}

module.exports = { RoaringBitmap };
