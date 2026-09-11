/**
 * Context Window Bit-Packed Variable-Length ZigZag Integer Compressor
 * Encodes signed context token offsets and deltas into compact unsigned integers using ZigZag mapping
 * and packs them via LEB128 varints, achieving high compression ratios with 100% roundtrip fidelity.
 */

class ZigZagIntegerCompressor {
  constructor() {}

  encodeZigZag(n) {
    // Maps 0 -> 0, -1 -> 1, 1 -> 2, -2 -> 3, 2 -> 4, ...
    return n >= 0 ? (2 * n) : (-2 * n - 1);
  }

  decodeZigZag(u) {
    return (u % 2 === 0) ? (u / 2) : (-(u + 1) / 2);
  }

  encodeVarint(u) {
    const bytes = [];
    let val = u >>> 0;
    while (val >= 0x80) {
      bytes.push((val & 0x7F) | 0x80);
      val = val >>> 7;
    }
    bytes.push(val & 0x7F);
    return bytes;
  }

  decodeVarint(buffer, offset = 0) {
    let result = 0;
    let shift = 0;
    let bytesRead = 0;

    while (offset < buffer.length) {
      const b = buffer[offset++];
      bytesRead++;
      result |= (b & 0x7F) << shift;
      if ((b & 0x80) === 0) {
        break;
      }
      shift += 7;
    }

    return { value: result >>> 0, bytesRead };
  }

  compressDeltas(integers) {
    if (!integers || integers.length === 0) return Buffer.alloc(0);

    const allBytes = [];
    let prev = 0;

    for (let i = 0; i < integers.length; i++) {
      const current = integers[i];
      const delta = current - prev;
      prev = current;

      const zz = this.encodeZigZag(delta);
      const varintBytes = this.encodeVarint(zz);
      allBytes.push(...varintBytes);
    }

    return Buffer.from(allBytes);
  }

  decompressDeltas(buffer) {
    if (!buffer || buffer.length === 0) return [];

    const integers = [];
    let offset = 0;
    let prev = 0;

    while (offset < buffer.length) {
      const { value: zz, bytesRead } = this.decodeVarint(buffer, offset);
      offset += bytesRead;

      const delta = this.decodeZigZag(zz);
      const current = prev + delta;
      integers.push(current);
      prev = current;
    }

    return integers;
  }
}

module.exports = { ZigZagIntegerCompressor };
