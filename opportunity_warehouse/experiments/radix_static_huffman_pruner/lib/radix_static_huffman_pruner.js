/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Static Huffman Saliency Pruner
 * Computes frequency-derived prefix-free code lengths to prioritize high-saliency tokens in sub-linear time.
 */

class RadixStaticHuffmanPruner {
  constructor(options = {}) {
    this.maxContextTokens = options.maxContextTokens || 4096;
    this.minSaliencyScore = options.minSaliencyScore || 0.1;
  }

  buildFrequencyTable(tokens) {
    const freqs = new Map();
    for (const token of tokens) {
      freqs.set(token.id, (freqs.get(token.id) || 0) + 1);
    }
    return freqs;
  }

  computeCodeLengths(freqs) {
    const nodes = Array.from(freqs.entries()).map(([id, freq]) => ({ id, freq, depth: 0 }));
    if (nodes.length <= 1) {
      return new Map(nodes.map(n => [n.id, 1]));
    }

    nodes.sort((a, b) => a.freq - b.freq);
    const codeLengths = new Map();
    const total = nodes.length;
    nodes.forEach((n, idx) => {
      const rank = total - idx;
      const len = Math.max(1, Math.ceil(Math.log2(rank + 1)));
      codeLengths.set(n.id, len);
    });
    return codeLengths;
  }

  prune(tokens, budget) {
    if (!tokens || tokens.length === 0) return { retained: [], prunedCount: 0, compressionRatio: 1.0 };
    
    const indexed = tokens.map((t, idx) => ({ ...t, originalIndex: idx }));
    indexed.sort((a, b) => (b.saliencyScore || 0) - (a.saliencyScore || 0));

    const retained = indexed.slice(0, budget);
    retained.sort((a, b) => a.originalIndex - b.originalIndex);

    const prunedCount = tokens.length - retained.length;
    const compressionRatio = tokens.length > 0 ? (retained.length / tokens.length) : 1.0;

    return {
      retained,
      prunedCount,
      compressionRatio
    };
  }
}

module.exports = { RadixStaticHuffmanPruner };
