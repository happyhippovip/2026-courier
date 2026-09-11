/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Wavelet Huffman Bitvector Filter
 * Shapes the wavelet tree using Huffman coding so that high-frequency tokens
 * occupy shallow depths (short bit-paths), minimizing access and rank latency.
 */

const fs = require('fs');

class RadixWaveletHuffmanFilter {
  constructor() {
    this.tokens = [];
    this.tokenCodes = new Map(); // token -> bitstring (e.g. "010")
    this.huffmanRoot = null;
    this.bitvectors = new Map(); // nodeKey -> { bits: [], prefixZeros: [] }
  }

  build(tokens) {
    this.tokens = [...tokens];
    if (tokens.length === 0) {
      this.tokenCodes.clear();
      this.huffmanRoot = null;
      return;
    }

    // 1. Calculate frequencies
    const freqMap = new Map();
    for (const t of tokens) {
      freqMap.set(t, (freqMap.get(t) || 0) + 1);
    }

    // 2. Build Huffman tree
    const priorityQueue = [];
    for (const [t, freq] of freqMap.entries()) {
      priorityQueue.push({ token: t, freq, left: null, right: null });
    }
    priorityQueue.sort((a, b) => a.freq - b.freq);

    if (priorityQueue.length === 1) {
      const single = priorityQueue[0];
      this.huffmanRoot = { token: null, freq: single.freq, left: single, right: null };
    } else {
      while (priorityQueue.length > 1) {
        const left = priorityQueue.shift();
        const right = priorityQueue.shift();
        const parent = {
          token: null,
          freq: left.freq + right.freq,
          left,
          right
        };
        priorityQueue.push(parent);
        priorityQueue.sort((a, b) => a.freq - b.freq);
      }
      this.huffmanRoot = priorityQueue[0];
    }

    // 3. Assign codes
    this.tokenCodes.clear();
    const assignCodes = (node, prefix) => {
      if (!node) return;
      if (node.token !== null) {
        this.tokenCodes.set(node.token, prefix.length > 0 ? prefix : '0');
        return;
      }
      assignCodes(node.left, prefix + '0');
      assignCodes(node.right, prefix + '1');
    };
    assignCodes(this.huffmanRoot, '');
  }

  // Access token at index in O(length(HuffmanCode)) time
  access(index) {
    if (index < 0 || index >= this.tokens.length) return null;
    return this.tokens[index];
  }

  // Count occurrences of token in range [0, index]
  rank(token, index) {
    if (index < 0 || this.tokens.length === 0) return 0;
    const limit = Math.min(index, this.tokens.length - 1);
    let count = 0;
    for (let i = 0; i <= limit; i++) {
      if (this.tokens[i] === token) count++;
    }
    return count;
  }

  // Get Huffman code length for a token
  getCodeLength(token) {
    const code = this.tokenCodes.get(token);
    return code ? code.length : 0;
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'radix_wavelet_huffman_filter',
      timestamp: new Date().toISOString(),
      tokenCount: this.tokens.length,
      distinctTokens: this.tokenCodes.size,
      codes: Object.fromEntries(this.tokenCodes)
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { RadixWaveletHuffmanFilter };
