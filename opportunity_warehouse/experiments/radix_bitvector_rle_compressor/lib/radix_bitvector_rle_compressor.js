/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Bit-Vector RLE Compressor
 * Implements Run-Length Encoding over sparse or dense bit-vectors for token presence bitmasks.
 */

class RadixBitVectorRLECompressor {
  constructor() {
    this.runs = [];
    this.totalBits = 0;
  }

  compress(bitString) {
    this.totalBits = bitString.length;
    this.runs = [];
    if (this.totalBits === 0) return Buffer.alloc(0);

    let currentBit = bitString[0];
    let currentRun = 1;

    for (let i = 1; i < bitString.length; i++) {
      if (bitString[i] === currentBit) {
        currentRun++;
      } else {
        this.runs.push({ bit: currentBit === '1' ? 1 : 0, count: currentRun });
        currentBit = bitString[i];
        currentRun = 1;
      }
    }
    this.runs.push({ bit: currentBit === '1' ? 1 : 0, count: currentRun });

    // Pack runs into compact byte buffer:
    // Header: 4 bytes totalBits
    // Per run: 1 byte (bit: 1 bit, count: 7 bits). If count > 127, multi-byte varint count
    const bytes = [];
    bytes.push(this.totalBits & 0xFF, (this.totalBits >> 8) & 0xFF, (this.totalBits >> 16) & 0xFF, (this.totalBits >> 24) & 0xFF);

    for (const r of this.runs) {
      let count = r.count;
      let first = true;
      while (count > 0 || first) {
        let chunk = Math.min(count, 0x3F); // 6 bits for chunk
        count -= chunk;
        const more = count > 0 ? 1 : 0;
        const byte = (r.bit << 7) | (more << 6) | (chunk & 0x3F);
        bytes.push(byte);
        first = false;
      }
    }

    return Buffer.from(bytes);
  }

  decompress(buf) {
    const bytes = Array.from(buf);
    if (bytes.length < 4) return '';

    const totalBits = bytes[0] | (bytes[1] << 8) | (bytes[2] << 16) | (bytes[3] << 24);
    let result = '';
    let idx = 4;

    while (idx < bytes.length && result.length < totalBits) {
      const b = bytes[idx++];
      const bit = (b >> 7) & 0x01;
      let more = (b >> 6) & 0x01;
      let count = b & 0x3F;

      while (more && idx < bytes.length) {
        const nextB = bytes[idx++];
        more = (nextB >> 6) & 0x01;
        count += (nextB & 0x3F);
      }

      result += bit === 1 ? '1'.repeat(count) : '0'.repeat(count);
    }

    return result.substring(0, totalBits);
  }

  calculateStats(originalBitString) {
    const rawBytes = Math.ceil(originalBitString.length / 8);
    const compressedBytes = this.runs.length; // Approximate
    const ratio = rawBytes > 0 ? (1 - compressedBytes / rawBytes) * 100 : 0;
    return {
      totalBits: this.totalBits,
      totalRuns: this.runs.length,
      rawBytes: rawBytes,
      compressedRuns: this.runs.length,
      efficiencyPct: Number(ratio.toFixed(2))
    };
  }
}

module.exports = { RadixBitVectorRLECompressor };
