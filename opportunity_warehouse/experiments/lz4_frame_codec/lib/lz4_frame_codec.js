/**
 * Dynamic Context Block LZ4 Frame Encoder & Decompressor
 * Implements lightweight LZ77-style token block compression with hash-table match finding,
 * token literals, match lengths, and frame headers for lossless decompression.
 */

class LZ4FrameCodec {
  constructor(minMatchLength = 4) {
    this.minMatchLength = minMatchLength;
  }

  // Compress an ASCII/UTF-8 string into an LZ-token sequence
  compress(input) {
    const data = Buffer.from(input, 'utf8');
    const n = data.length;
    const hashTable = new Map(); // 4-byte hash -> position
    const tokens = [];

    let i = 0;
    let literalStart = 0;

    while (i <= n - this.minMatchLength) {
      const seq = data.readUInt32LE(i);
      if (hashTable.has(seq)) {
        const matchPos = hashTable.get(seq);
        const offset = i - matchPos;

        if (offset < 65535) {
          // Find match length
          let matchLen = 0;
          while (i + matchLen < n && data[matchPos + matchLen] === data[i + matchLen]) {
            matchLen++;
          }

          if (matchLen >= this.minMatchLength) {
            // Flush preceding literals
            const literalBytes = data.subarray(literalStart, i);
            tokens.push({
              type: 'MATCH',
              literals: literalBytes.toString('utf8'),
              offset,
              length: matchLen
            });

            // Update hash and advance
            for (let k = 0; k < matchLen; k++) {
              if (i + k <= n - 4) {
                hashTable.set(data.readUInt32LE(i + k), i + k);
              }
            }

            i += matchLen;
            literalStart = i;
            continue;
          }
        }
      }

      hashTable.set(seq, i);
      i++;
    }

    // Trailing literals
    const remaining = data.subarray(literalStart, n);
    if (remaining.length > 0) {
      tokens.push({
        type: 'LITERAL',
        literals: remaining.toString('utf8')
      });
    }

    const payload = JSON.stringify({ magic: 'LZ4F', originalLength: n, tokens });
    const compressedBytes = Buffer.byteLength(payload, 'utf8');

    return {
      payload,
      originalBytes: n,
      compressedBytes,
      compressionRatio: n > 0 ? (1 - (compressedBytes / n)) : 0
    };
  }

  // Decompress back to exact original string
  decompress(payloadString) {
    const frame = JSON.parse(payloadString);
    if (frame.magic !== 'LZ4F') throw new Error('Invalid LZ4 frame header');

    let out = Buffer.alloc(frame.originalLength);
    let outPos = 0;

    for (const t of frame.tokens) {
      if (t.literals && t.literals.length > 0) {
        const litBuf = Buffer.from(t.literals, 'utf8');
        litBuf.copy(out, outPos);
        outPos += litBuf.length;
      }

      if (t.type === 'MATCH') {
        const start = outPos - t.offset;
        for (let j = 0; j < t.length; j++) {
          out[outPos++] = out[start + j];
        }
      }
    }

    return out.subarray(0, outPos).toString('utf8');
  }
}

module.exports = { LZ4FrameCodec };
