/**
 * Context Window Token Dynamic Bounded Fast Succinct Suffix Wavelet Run-Length Compressor
 * Computes Burrows-Wheeler Transform (BWT) over token arrays, partitions into run-length
 * encoded segments (symbol, runLength), and provides lossless decompression and frequency queries.
 */

const fs = require('fs');

class SuffixWaveletRLECompressor {
  constructor() {
    this.runs = [];
    this.primaryIndex = -1;
    this.originalLength = 0;
  }

  // Compute Burrows-Wheeler Transform of an array of tokens
  computeBWT(tokens) {
    const n = tokens.length;
    if (n === 0) return { bwt: [], primaryIndex: 0 };

    // Form cyclical rotations represented by indices
    const rotations = Array.from({ length: n }, (_, i) => i);
    rotations.sort((a, b) => {
      for (let k = 0; k < n; k++) {
        const valA = tokens[(a + k) % n];
        const valB = tokens[(b + k) % n];
        if (valA !== valB) return valA < valB ? -1 : 1;
      }
      return 0;
    });

    const bwt = [];
    let primaryIndex = 0;
    for (let i = 0; i < n; i++) {
      const rot = rotations[i];
      if (rot === 0) primaryIndex = i;
      bwt.push(tokens[(rot + n - 1) % n]);
    }
    return { bwt, primaryIndex };
  }

  // Invert Burrows-Wheeler Transform
  invertBWT(bwt, primaryIndex) {
    const n = bwt.length;
    if (n === 0) return [];

    // LF-mapping:
    // Count occurrences of each symbol
    const count = new Map();
    for (const sym of bwt) {
      count.set(sym, (count.get(sym) || 0) + 1);
    }

    const sortedSymbols = Array.from(count.keys()).sort((a, b) => (a < b ? -1 : 1));
    const firstOccur = new Map();
    let tot = 0;
    for (const sym of sortedSymbols) {
      firstOccur.set(sym, tot);
      tot += count.get(sym);
    }

    const rankInBwt = new Array(n);
    const currCount = new Map();
    for (let i = 0; i < n; i++) {
      const sym = bwt[i];
      const r = currCount.get(sym) || 0;
      rankInBwt[i] = r;
      currCount.set(sym, r + 1);
    }

    // LF mapping array
    const LF = new Array(n);
    for (let i = 0; i < n; i++) {
      LF[i] = firstOccur.get(bwt[i]) + rankInBwt[i];
    }

    // Reconstruct tokens backwards from primaryIndex
    const result = new Array(n);
    let curr = primaryIndex;
    for (let i = n - 1; i >= 0; i--) {
      result[i] = bwt[curr];
      curr = LF[curr];
    }

    return result;
  }

  // Compress token stream into RLE of BWT
  compress(tokens) {
    this.originalLength = tokens.length;
    if (tokens.length === 0) {
      this.runs = [];
      this.primaryIndex = 0;
      return { runs: [], primaryIndex: 0, originalLength: 0, runCount: 0, compressionRatio: 1.0 };
    }

    const { bwt, primaryIndex } = this.computeBWT(tokens);
    this.primaryIndex = primaryIndex;

    // Run-length encode BWT
    const runs = [];
    let currentSym = bwt[0];
    let currentLen = 1;

    for (let i = 1; i < bwt.length; i++) {
      if (bwt[i] === currentSym) {
        currentLen++;
      } else {
        runs.push({ symbol: currentSym, length: currentLen });
        currentSym = bwt[i];
        currentLen = 1;
      }
    }
    runs.push({ symbol: currentSym, length: currentLen });
    this.runs = runs;

    const compressedSize = runs.length * 2; // (symbol, length) pairs
    const compressionRatio = compressedSize / (this.originalLength || 1);

    return {
      runs: this.runs,
      primaryIndex: this.primaryIndex,
      originalLength: this.originalLength,
      runCount: this.runs.length,
      compressionRatio
    };
  }

  // Lossless decompression
  decompress() {
    if (this.originalLength === 0) return [];

    // Expand runs back to BWT
    const bwt = [];
    for (const run of this.runs) {
      for (let i = 0; i < run.length; i++) {
        bwt.push(run.symbol);
      }
    }

    return this.invertBWT(bwt, this.primaryIndex);
  }

  // Query frequency of symbol across runs
  querySymbolFrequency(symbol) {
    let total = 0;
    for (const run of this.runs) {
      if (run.symbol === symbol) total += run.length;
    }
    return total;
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'suffix_wavelet_rle_compressor',
      timestamp: new Date().toISOString(),
      originalLength: this.originalLength,
      runCount: this.runs.length,
      compressionRatio: this.runs.length * 2 / (this.originalLength || 1),
      primaryIndex: this.primaryIndex
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { SuffixWaveletRLECompressor };
