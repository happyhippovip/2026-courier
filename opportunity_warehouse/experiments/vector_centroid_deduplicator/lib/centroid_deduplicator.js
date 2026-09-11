/**
 * Context Window Semantic Anchoring & Vector Centroid Deduplicator
 * Extracts simulated n-gram feature vectors, computes cosine distances,
 * clusters semantically redundant retrieved chunks, and retains only the centroid representation.
 */

class VectorCentroidDeduplicator {
  constructor() {}

  extractFeatureVector(text = '') {
    const words = text.toLowerCase().replace(/[^a-z0-9_]/g, ' ').split(/\s+/).filter(w => w.length > 2);
    const vector = new Map();
    for (const w of words) {
      vector.set(w, (vector.get(w) || 0) + 1);
    }
    return vector;
  }

  computeCosineSimilarity(vecA, vecB) {
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (const val of vecA.values()) {
      normA += val * val;
    }
    for (const val of vecB.values()) {
      normB += val * val;
    }

    if (normA === 0 || normB === 0) return 0;

    for (const [term, countA] of vecA.entries()) {
      if (vecB.has(term)) {
        dotProduct += countA * vecB.get(term);
      }
    }

    return Number((dotProduct / (Math.sqrt(normA) * Math.sqrt(normB))).toFixed(3));
  }

  clusterAndDeduplicate(chunks = [], similarityThreshold = 0.65) {
    const chunkVectors = chunks.map(c => ({
      id: c.id,
      text: c.text,
      tokens: Math.max(1, Math.round(c.text.length / 4)),
      vector: this.extractFeatureVector(c.text)
    }));

    const clusters = []; // Array of arrays of chunk objects
    const visited = new Set();

    for (let i = 0; i < chunkVectors.length; i++) {
      if (visited.has(chunkVectors[i].id)) continue;

      const cluster = [chunkVectors[i]];
      visited.add(chunkVectors[i].id);

      for (let j = i + 1; j < chunkVectors.length; j++) {
        if (visited.has(chunkVectors[j].id)) continue;

        const sim = this.computeCosineSimilarity(chunkVectors[i].vector, chunkVectors[j].vector);
        if (sim >= similarityThreshold) {
          cluster.push(chunkVectors[j]);
          visited.add(chunkVectors[j].id);
        }
      }

      clusters.push(cluster);
    }

    // Select centroid (chunk with largest word diversity / length) for each cluster
    const retainedChunks = [];
    const prunedChunks = [];

    for (const cl of clusters) {
      cl.sort((a, b) => b.tokens - a.tokens); // longest/most informative chunk is centroid
      const centroid = cl[0];
      retainedChunks.push({
        id: centroid.id,
        text: centroid.text,
        tokens: centroid.tokens,
        subsumedChunkCount: cl.length - 1
      });

      for (let k = 1; k < cl.length; k++) {
        prunedChunks.push({
          id: cl[k].id,
          tokens: cl[k].tokens,
          subsumedByCentroid: centroid.id
        });
      }
    }

    const origTokens = chunkVectors.reduce((acc, c) => acc + c.tokens, 0);
    const finalTokens = retainedChunks.reduce((acc, c) => acc + c.tokens, 0);

    return {
      originalChunksCount: chunks.length,
      retainedCentroidsCount: retainedChunks.length,
      prunedDuplicatesCount: prunedChunks.length,
      originalTokens: origTokens,
      finalTokens: finalTokens,
      tokensSaved: origTokens - finalTokens,
      savingsPercent: origTokens > 0 ? Number((((origTokens - finalTokens) / origTokens) * 100).toFixed(1)) : 0,
      retainedCentroids: retainedChunks,
      prunedDetails: prunedChunks
    };
  }
}

module.exports = { VectorCentroidDeduplicator };
