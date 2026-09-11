/**
 * Cross-Model Semantic Embedding Align & Fusion Matrix
 * Aligns multi-model embedding vector spaces (different dimensions/bases) using
 * affine projection matrices and weighted semantic centroid fusion.
 */

class SemanticEmbeddingFusion {
  constructor() {}

  computeNorm(vec) {
    const sumSq = vec.reduce((acc, v) => acc + v * v, 0);
    return Math.sqrt(sumSq) || 1e-12;
  }

  normalizeVector(vec) {
    const norm = this.computeNorm(vec);
    return vec.map(v => v / norm);
  }

  computeCosineSimilarity(v1, v2) {
    if (v1.length !== v2.length) {
      throw new Error('Vector lengths must match: ' + v1.length + ' vs ' + v2.length);
    }
    let dot = 0;
    let norm1 = 0;
    let norm2 = 0;
    for (let i = 0; i < v1.length; i++) {
      dot += v1[i] * v2[i];
      norm1 += v1[i] * v1[i];
      norm2 += v2[i] * v2[i];
    }
    const denom = Math.sqrt(norm1) * Math.sqrt(norm2);
    return denom === 0 ? 0 : Number((dot / denom).toFixed(4));
  }

  projectVector(inputVec, projectionMatrix) {
    const outDim = projectionMatrix.length;
    const inDim = projectionMatrix[0].length;
    if (inputVec.length !== inDim) {
      throw new Error('Input vector dim ' + inputVec.length + ' does not match matrix cols ' + inDim);
    }
    const out = new Array(outDim).fill(0);
    for (let i = 0; i < outDim; i++) {
      let sum = 0;
      for (let j = 0; j < inDim; j++) {
        sum += projectionMatrix[i][j] * inputVec[j];
      }
      out[i] = sum;
    }
    return this.normalizeVector(out);
  }

  fuseEmbeddings(weightedEmbeddings) {
    if (!weightedEmbeddings || weightedEmbeddings.length === 0) {
      throw new Error('Empty embeddings array');
    }
    const dim = weightedEmbeddings[0].vector.length;
    const fused = new Array(dim).fill(0);
    let totalWeight = 0;

    for (const item of weightedEmbeddings) {
      const w = item.weight || 1.0;
      totalWeight += w;
      for (let d = 0; d < dim; d++) {
        fused[d] += item.vector[d] * w;
      }
    }

    const unweighted = fused.map(v => v / totalWeight);
    return this.normalizeVector(unweighted);
  }
}

module.exports = { SemanticEmbeddingFusion };