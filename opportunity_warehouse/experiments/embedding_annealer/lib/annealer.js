/**
 * Context Window Quantized Cosine Vector Embedding Annealer & Redundancy Pruner
 * Quantizes float32 embeddings to int8 representation for sub-millisecond similarity math,
 * executing Maximal Marginal Relevance (MMR) and threshold annealing to maximize semantic diversity under token budgets.
 */

class EmbeddingAnnealer {
  constructor(options = {}) {
    this.redundancyThreshold = options.redundancyThreshold || 0.85;
  }

  quantizeToInt8(floatVector) {
    let maxAbs = 0;
    for (let i = 0; i < floatVector.length; i++) {
      const abs = Math.abs(floatVector[i]);
      if (abs > maxAbs) maxAbs = abs;
    }
    if (maxAbs === 0) maxAbs = 1;

    const scale = 127 / maxAbs;
    const quantized = new Int8Array(floatVector.length);
    for (let i = 0; i < floatVector.length; i++) {
      quantized[i] = Math.round(floatVector[i] * scale);
    }
    return { quantized, scale };
  }

  cosineSimilarity(qA, qB) {
    const vA = qA.quantized || qA;
    const vB = qB.quantized || qB;
    const len = Math.min(vA.length, vB.length);

    let dot = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < len; i++) {
      const a = vA[i];
      const b = vB[i];
      dot += a * b;
      normA += a * a;
      normB += b * b;
    }

    if (normA === 0 || normB === 0) return 0;
    return Number((dot / (Math.sqrt(normA) * Math.sqrt(normB))).toFixed(4));
  }

  pruneRedundant(chunks, threshold = this.redundancyThreshold) {
    const retained = [];
    const pruned = [];

    for (let i = 0; i < chunks.length; i++) {
      const candidate = chunks[i];
      let isDuplicate = false;

      for (const selected of retained) {
        const sim = this.cosineSimilarity(candidate.embedding, selected.embedding);
        if (sim >= threshold) {
          isDuplicate = true;
          pruned.push({
            id: candidate.id,
            similarTo: selected.id,
            similarity: sim
          });
          break;
        }
      }

      if (!isDuplicate) {
        retained.push(candidate);
      }
    }

    return {
      totalEvaluated: chunks.length,
      retainedCount: retained.length,
      prunedCount: pruned.length,
      retained,
      pruned
    };
  }

  maximalMarginalRelevance(queryVec, candidates, k = 3, lambda = 0.6) {
    const selected = [];
    const remaining = [...candidates];

    while (selected.length < k && remaining.length > 0) {
      let bestScore = -Infinity;
      let bestIndex = -1;

      for (let i = 0; i < remaining.length; i++) {
        const item = remaining[i];
        const relevance = this.cosineSimilarity(item.embedding, queryVec);

        let maxRedundancy = 0;
        for (const s of selected) {
          const sim = this.cosineSimilarity(item.embedding, s.embedding);
          if (sim > maxRedundancy) maxRedundancy = sim;
        }

        const mmrScore = lambda * relevance - (1 - lambda) * maxRedundancy;
        if (mmrScore > bestScore) {
          bestScore = mmrScore;
          bestIndex = i;
        }
      }

      if (bestIndex !== -1) {
        selected.push({
          ...remaining[bestIndex],
          mmrScore: Number(bestScore.toFixed(4))
        });
        remaining.splice(bestIndex, 1);
      } else {
        break;
      }
    }

    return selected;
  }
}

module.exports = { EmbeddingAnnealer };
