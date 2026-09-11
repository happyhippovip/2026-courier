/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Variable-Byte Integer Compressor
 * Implements 7-bit variable-length byte integer compression with MSB continuation signaling.
 */

class RadixVByteCompressor {
  constructor() {
    this.buffer = [];
    this.tokenCount = 0;
  }

  encodeInteger(val) {
    if (val < 0) val = 0;
    const bytes = [];
    while (val >= 128) {
      bytes.push((val & 0x7F) | 0x80); // Continuation bit 1
      val = Math.floor(val / 128);
    }
    bytes.push(val & 0x7F); // Terminal byte MSB 0
    return bytes;
  }

  decodeBytes(bytes) {
    const numbers = [];
    let current = 0;
    let shift = 0;

    for (let i = 0; i < bytes.length; i++) {
      const b = bytes[i];
      current += (b & 0x7F) * Math.pow(128, shift);
      if ((b & 0x80) === 0) {
        // Terminal byte reached
        numbers.push(current);
        current = 0;
        shift = 0;
      } else {
        shift++;
      }
    }
    return numbers;
  }

  compress(tokens) {
    this.tokenCount = tokens.length;
    this.buffer = [];
    for (const t of tokens) {
      const val = typeof t === 'number' ? t : (t.id || 0);
      const encoded = this.encodeInteger(val);
      for (const b of encoded) {
        this.buffer.push(b);
      }
    }
    return Buffer.from(this.buffer);
  }

  decompress(buf) {
    const byteArr = Array.from(buf);
    return this.decodeBytes(byteArr);
  }

  calculateStats(originalTokens) {
    const rawByteSize = originalTokens.length * 4; // 32-bit baseline
    const compressedByteSize = this.buffer.length;
    const ratio = rawByteSize > 0 ? (1 - compressedByteSize / rawByteSize) * 100 : 0;
    return {
      tokenCount: this.tokenCount,
      rawBytes: rawByteSize,
      compressedBytes: compressedByteSize,
      compressionRatioPct: Number(ratio.toFixed(2))
    };
  }
}

module.exports = { RadixVByteCompressor };
