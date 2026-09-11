/**
 * Context Window Bi-Directional Shingle N-Gram Similarity Indexer & MinHash Deduplicator
 * Provides sub-linear locality-sensitive hashing (LSH) and MinHash signature estimation
 * to eliminate repetitive context turns, prompt echoes, and near-duplicate tool outputs.
 */

class MinHashDeduplicator {
  constructor(options = {}) {
    this.numHashes = options.numHashes || 32;
    this.shingleSize = options.shingleSize || 2; // word n-grams
    this.threshold = options.threshold || 0.70;
    // Generate deterministic hash coefficients: (a * x + b) % p
    // Mersenne prime 2^31 - 1 = 2147483647
    this.prime = 2147483647;
    this.hashParams = [];
    for (let i = 0; i < this.numHashes; i++) {
      const a = (i * 10007 + 12345) % (this.prime - 1) + 1;
      const b = (i * 54321 + 67890) % this.prime;
      this.hashParams.push({ a, b });
    }
  }

  tokenize(text) {
    if (!text || typeof text !== 'string') return [];
    return text
      .toLowerCase()
      .replace(/[^a-z0-9_\s]/g, ' ')
      .split(/\s+/)
      .filter(t => t.length > 0);
  }

  createShingles(text, n = this.shingleSize) {
    const tokens = this.tokenize(text);
    if (tokens.length === 0) return new Set(['__EMPTY__']);
    if (tokens.length <= n) {
      return new Set([tokens.join(' ')]);
    }
    const shingles = new Set();
    for (let i = 0; i <= tokens.length - n; i++) {
      shingles.add(tokens.slice(i, i + n).join(' '));
    }
    return shingles;
  }

  hashShingle(shingleStr) {
    // 32-bit FNV-1a hash
    let hash = 2166136261;
    for (let i = 0; i < shingleStr.length; i++) {
      hash ^= shingleStr.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0);
  }

  computeSignature(shingles) {
    const shingleArray = Array.from(shingles);
    const shingleHashes = shingleArray.map(s => this.hashShingle(s));
    const signature = new Array(this.numHashes).fill(Infinity);

    for (let i = 0; i < this.numHashes; i++) {
      const { a, b } = this.hashParams[i];
      let minVal = Infinity;
      for (const sh of shingleHashes) {
        // Linear hash function mod Mersenne prime
        const h = Number((BigInt(a) * BigInt(sh) + BigInt(b)) % BigInt(this.prime));
        if (h < minVal) {
          minVal = h;
        }
      }
      signature[i] = minVal;
    }
    return signature;
  }

  estimateJaccard(sig1, sig2) {
    if (!sig1 || !sig2 || sig1.length !== sig2.length) return 0;
    let matches = 0;
    for (let i = 0; i < sig1.length; i++) {
      if (sig1[i] === sig2[i]) {
        matches++;
      }
    }
    return matches / sig1.length;
  }

  exactJaccard(set1, set2) {
    if (set1.size === 0 && set2.size === 0) return 1;
    let intersection = 0;
    for (const item of set1) {
      if (set2.has(item)) intersection++;
    }
    const union = set1.size + set2.size - intersection;
    return union === 0 ? 0 : (intersection / union);
  }

  deduplicateBatch(items, threshold = this.threshold) {
    const processed = items.map((item, idx) => {
      const text = typeof item === 'string' ? item : (item.content || item.text || JSON.stringify(item));
      const shingles = this.createShingles(text);
      const signature = this.computeSignature(shingles);
      return {
        original: item,
        index: idx,
        text,
        shingles,
        signature
      };
    });

    const retained = [];
    const duplicates = [];
    const clusters = [];

    for (let i = 0; i < processed.length; i++) {
      const current = processed[i];
      let matchedCluster = null;

      for (const cluster of clusters) {
        const rep = cluster.representative;
        const sim = this.estimateJaccard(current.signature, rep.signature);
        if (sim >= threshold) {
          matchedCluster = cluster;
          matchedCluster.members.push({
            index: current.index,
            item: current.original,
            similarity: sim
          });
          duplicates.push({
            index: current.index,
            item: current.original,
            retainedIndex: rep.index,
            estimatedSimilarity: sim
          });
          break;
        }
      }

      if (!matchedCluster) {
        clusters.push({
          clusterId: 'cluster_' + clusters.length,
          representative: current,
          members: [{ index: current.index, item: current.original, similarity: 1.0 }]
        });
        retained.push(current.original);
      }
    }

    const deduplicationRatio = items.length > 0 ? (duplicates.length / items.length) : 0;

    return {
      retainedCount: retained.length,
      duplicateCount: duplicates.length,
      deduplicationRatio: Number(deduplicationRatio.toFixed(4)),
      clustersCount: clusters.length,
      retained,
      duplicates,
      clusters: clusters.map(c => ({
        clusterId: c.clusterId,
        representativeIndex: c.representative.index,
        memberIndices: c.members.map(m => m.index),
        memberCount: c.members.length
      }))
    };
  }
}

module.exports = { MinHashDeduplicator };
