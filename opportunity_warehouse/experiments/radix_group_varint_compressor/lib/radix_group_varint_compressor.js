/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Group-Varint Compressor
 * Implements Group Varint encoding: 4 integers grouped per control byte (2 bits per integer length: 1, 2, 3, or 4 bytes).
 */

class RadixGroupVarintCompressor {
  constructor() {
    this.buffer = [];
    this.tokenCount = 0;
  }

  getByteLength(val) {
    if (val < 256) return 1;
    if (val < 65536) return 2;
    if (val < 16777216) return 3;
    return 4;
  }

  encodeQuad(quad) {
    while (quad.length < 4) {
      quad.push(0);
    }
    const lengths = quad.map(v => this.getByteLength(v));
    // 2 bits each: (len - 1)
    const controlByte = ((lengths[0] - 1) << 6) |
                        ((lengths[1] - 1) << 4) |
                        ((lengths[2] - 1) << 2) |
                        (lengths[3] - 1);

    const dataBytes = [];
    for (let i = 0; i < 4; i++) {
      let val = quad[i];
      const len = lengths[i];
      for (let b = 0; b < len; b++) {
        dataBytes.push(val & 0xFF);
        val = Math.floor(val / 256);
      }
    }

    return [controlByte, ...dataBytes];
  }

  compress(tokens) {
    this.tokenCount = tokens.length;
    this.buffer = [];

    // Store original token length as prefix 4 bytes
    const len = tokens.length;
    this.buffer.push(len & 0xFF, (len >> 8) & 0xFF, (len >> 16) & 0xFF, (len >> 24) & 0xFF);

    for (let i = 0; i < tokens.length; i += 4) {
      const quad = [];
      for (let j = 0; j < 4; j++) {
        if (i + j < tokens.length) {
          const t = tokens[i + j];
          quad.push(typeof t === 'number' ? t : (t.id || 0));
        }
      }
      const encodedQuad = this.encodeQuad(quad);
      for (const b of encodedQuad) {
        this.buffer.push(b);
      }
    }

    return Buffer.from(this.buffer);
  }

  decompress(buf) {
    const bytes = Array.from(buf);
    if (bytes.length < 4) return [];

    const totalTokens = bytes[0] | (bytes[1] << 8) | (bytes[2] << 16) | (bytes[3] << 24);
    const decoded = [];
    let idx = 4;

    while (idx < bytes.length && decoded.length < totalTokens) {
      const control = bytes[idx++];
      const l0 = ((control >> 6) & 0x03) + 1;
      const l1 = ((control >> 4) & 0x03) + 1;
      const l2 = ((control >> 2) & 0x03) + 1;
      const l3 = (control & 0x03) + 1;
      const lens = [l0, l1, l2, l3];

      for (let k = 0; k < 4; k++) {
        if (decoded.length >= totalTokens) break;
        const len = lens[k];
        let val = 0;
        let shift = 0;
        for (let b = 0; b < len; b++) {
          val += bytes[idx++] * Math.pow(256, shift);
          shift++;
        }
        decoded.push(val);
      }
    }

    return decoded;
  }

  calculateStats(originalTokens) {
    const rawByteSize = originalTokens.length * 4;
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

module.exports = { RadixGroupVarintCompressor };
