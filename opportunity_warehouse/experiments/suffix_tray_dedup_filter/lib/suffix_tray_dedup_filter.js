/**
 * Context Window Token Dynamic Bounded Fast Succinct Suffix Tray Deduplication Filter
 * Organizes token sequence suffixes into partitioned hash trays to detect
 * repetitive sub-sequences in O(1) time and eliminate prompt inflation.
 */

class SuffixTrayDedupFilter {
  constructor(trayCount = 16, shingleSize = 3) {
    this.trayCount = trayCount;
    this.shingleSize = shingleSize;
    this.trays = Array.from({ length: trayCount }, () => new Map()); // trayIndex -> Map(shingleHash, metadata)
    this.totalTokensProcessed = 0;
    this.duplicatesDetected = 0;
  }

  _hashShingle(shingle) {
    let hash = 0;
    const str = shingle.join('||');
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash);
  }

  ingest(tokens, chunkId) {
    let duplicateHits = 0;
    const shingles = [];

    for (let i = 0; i <= tokens.length - this.shingleSize; i++) {
      const shingle = tokens.slice(i, i + this.shingleSize);
      const h = this._hashShingle(shingle);
      const trayIdx = h % this.trayCount;
      const tray = this.trays[trayIdx];

      if (tray.has(h)) {
        duplicateHits++;
        this.duplicatesDetected++;
      } else {
        tray.set(h, { chunkId, index: i });
      }
      shingles.push(h);
    }

    this.totalTokensProcessed += tokens.length;
    const duplicateRatio = tokens.length > 0 ? Number((duplicateHits / Math.max(1, tokens.length - this.shingleSize + 1)).toFixed(4)) : 0;

    return {
      chunkId,
      tokenCount: tokens.length,
      duplicateHits,
      duplicateRatio,
      isDuplicateCandidate: duplicateRatio > 0.5
    };
  }

  getMetrics() {
    let totalEntries = 0;
    for (const tray of this.trays) totalEntries += tray.size;
    return {
      trayCount: this.trayCount,
      totalEntries,
      totalTokensProcessed: this.totalTokensProcessed,
      duplicatesDetected: this.duplicatesDetected
    };
  }
}

module.exports = { SuffixTrayDedupFilter };
