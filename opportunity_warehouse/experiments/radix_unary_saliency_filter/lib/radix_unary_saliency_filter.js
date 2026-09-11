/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Unary Variable-Length Saliency Filter
 * Encodes token saliency indices into compact unary bit vectors with radix boundary checkpoints.
 */

class RadixUnarySaliencyFilter {
  constructor(options = {}) {
    this.radixInterval = options.radixInterval || 16;
    this.bitstream = '';
    this.offsets = [];
    this.tokenCount = 0;
  }

  encode(tokens) {
    this.bitstream = '';
    this.offsets = [];
    this.tokenCount = tokens.length;

    for (let i = 0; i < tokens.length; i++) {
      if (i % this.radixInterval === 0) {
        this.offsets.push({ index: i, bitOffset: this.bitstream.length });
      }
      const val = Math.max(0, Math.floor(tokens[i].saliencyRank || 0));
      // Unary encoding: val zeros followed by 1
      this.bitstream += '0'.repeat(val) + '1';
    }
  }

  decodeAt(index) {
    if (index < 0 || index >= this.tokenCount) return null;
    const checkpointIdx = Math.floor(index / this.radixInterval);
    const cp = this.offsets[checkpointIdx];
    let bitPos = cp.bitOffset;
    let currIdx = cp.index;

    while (currIdx < index) {
      // Advance to next '1'
      while (bitPos < this.bitstream.length && this.bitstream[bitPos] === '0') {
        bitPos++;
      }
      bitPos++; // skip '1'
      currIdx++;
    }

    let zeroCount = 0;
    while (bitPos < this.bitstream.length && this.bitstream[bitPos] === '0') {
      zeroCount++;
      bitPos++;
    }
    return zeroCount;
  }
}

module.exports = { RadixUnarySaliencyFilter };
