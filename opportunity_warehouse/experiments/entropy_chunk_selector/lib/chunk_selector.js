/**
 * Context Window Entropy-Weighted Chunk Selector
 * Evaluates Shannon informational entropy and lexical uniqueness of candidate context chunks,
 * packing highest-entropy informative chunks into strict token budgets while preserving
 * global chronological sequence.
 */

class EntropyChunkSelector {
  constructor() {}

  computeShannonEntropy(text = '') {
    if (!text || text.length === 0) return 0;
    const freq = {};
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      freq[c] = (freq[c] || 0) + 1;
    }
    const len = text.length;
    let entropy = 0;
    for (const count of Object.values(freq)) {
      const p = count / len;
      entropy -= p * Math.log2(p);
    }
    return Number(entropy.toFixed(4));
  }

  evaluateChunk(chunk, index) {
    const text = chunk.text || '';
    const tokens = Math.max(1, Math.round(text.length / 4));
    const entropy = this.computeShannonEntropy(text);
    const words = text.split(/\s+/).filter(Boolean);
    const uniqueWords = new Set(words);
    const vocabRichness = words.length === 0 ? 0 : Number((uniqueWords.size / words.length).toFixed(3));
    const score = Number((entropy * (1 + vocabRichness)).toFixed(4));

    return {
      id: chunk.id || ('chunk_' + index),
      originalIndex: index,
      text,
      tokens,
      entropy,
      vocabRichness,
      densityScore: score
    };
  }

  packBudget(chunks = [], tokenBudget = 100) {
    const evaluated = chunks.map((c, i) => this.evaluateChunk(c, i));

    // Rank by densityScore descending
    const sorted = [...evaluated].sort((a, b) => b.densityScore - a.densityScore);

    const selected = [];
    let usedTokens = 0;

    for (const item of sorted) {
      if (usedTokens + item.tokens <= tokenBudget) {
        selected.push(item);
        usedTokens += item.tokens;
      }
    }

    // Re-sort selected chunks by original chronological index
    selected.sort((a, b) => a.originalIndex - b.originalIndex);

    return {
      tokenBudget,
      usedTokens,
      utilizationPercent: Number(((usedTokens / tokenBudget) * 100).toFixed(1)),
      selectedCount: selected.length,
      totalCandidateCount: chunks.length,
      selectedChunks: selected
    };
  }
}

module.exports = { EntropyChunkSelector };