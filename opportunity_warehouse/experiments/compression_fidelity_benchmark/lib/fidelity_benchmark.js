/**
 * Context Window Semantic Compression Ratio & Fidelity Benchmark
 * Measures semantic meaning retention, invariant preservation, and quality index
 * across various context pruning aggressiveness levels.
 */

class CompressionFidelityBenchmark {
  constructor() {}

  checkInvariantPreservation(originalText = '', prunedText = '', criticalInvariants = []) {
    const results = [];
    for (const inv of criticalInvariants) {
      const inOriginal = originalText.includes(inv);
      const inPruned = prunedText.includes(inv);
      results.push({
        invariant: inv,
        inOriginal,
        preserved: inPruned,
        status: (inOriginal && inPruned) ? 'PASS' : (inOriginal && !inPruned ? 'VIOLATION' : 'N/A')
      });
    }
    const violations = results.filter(r => r.status === 'VIOLATION').length;
    return {
      allPreserved: violations === 0,
      violationCount: violations,
      details: results
    };
  }

  calculateWordOverlapFidelity(originalText = '', prunedText = '') {
    const tokenize = str => str.toLowerCase().replace(/[^a-z0-9_]/g, ' ').split(/\s+/).filter(Boolean);
    const origWords = new Set(tokenize(originalText));
    const prunedWords = tokenize(prunedText);

    if (origWords.size === 0 || prunedWords.length === 0) return 0;

    let match = 0;
    for (const w of prunedWords) {
      if (origWords.has(w)) match++;
    }

    return Number(Math.min(1.0, (match / prunedWords.length)).toFixed(3));
  }

  evaluateFidelityBenchmark(originalText = '', prunedText = '', criticalInvariants = []) {
    const origTokens = Math.max(1, Math.round(originalText.length / 4));
    const prunedTokens = Math.max(1, Math.round(prunedText.length / 4));

    const compressionRatio = Number((prunedTokens / origTokens).toFixed(3));
    const tokenSavingsPercent = Number((((origTokens - prunedTokens) / origTokens) * 100).toFixed(1));

    const invariantCheck = this.checkInvariantPreservation(originalText, prunedText, criticalInvariants);
    const semanticOverlap = this.calculateWordOverlapFidelity(originalText, prunedText);

    // Quality Index: Fidelity penalized if invariants violated
    // Q = semanticOverlap * (1.0 - 0.5 * violationCount)
    const qualityIndex = Number(Math.max(0, semanticOverlap * (invariantCheck.allPreserved ? 1.0 : 0.2)).toFixed(3));

    return {
      originalTokens: origTokens,
      prunedTokens: prunedTokens,
      compressionRatio,
      tokenSavingsPercent,
      semanticFidelityScore: semanticOverlap,
      invariantsPreserved: invariantCheck.allPreserved,
      qualityIndex,
      isAcceptable: invariantCheck.allPreserved && qualityIndex >= 0.70,
      invariantDetails: invariantCheck.details
    };
  }
}

module.exports = { CompressionFidelityBenchmark };
