/**
 * entropy_measurer.js - Context Entropy & Information Density Measurer
 * Calculates Shannon entropy, redundancy ratios, and information density scores for prompts.
 */
class ContextEntropyMeasurer {
  constructor(options = {}) {
    this.options = options;
  }

  calculateShannonEntropy(text) {
    if (!text || typeof text !== 'string' || text.length === 0) return 0;
    const freq = {};
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      freq[c] = (freq[c] || 0) + 1;
    }

    const len = text.length;
    let entropy = 0;
    for (const char in freq) {
      const p = freq[char] / len;
      entropy -= p * Math.log2(p);
    }
    return +entropy.toFixed(4);
  }

  calculateRedundancyRatio(text) {
    if (!text || text.length < 20) return 0;
    const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length === 0) return 0;

    const uniqueLines = new Set(lines);
    const lineRedundancy = (lines.length - uniqueLines.size) / lines.length;

    // Check repetitive whitespace or repeated chars
    const repeatedCharMatches = text.match(/(.)\1{4,}/g) || [];
    const repeatedCharLength = repeatedCharMatches.reduce((acc, m) => acc + m.length, 0);
    const charRedundancy = repeatedCharLength / text.length;

    const combined = Math.min(1.0, (lineRedundancy * 0.7) + (charRedundancy * 0.3));
    return +combined.toFixed(4);
  }

  calculateInformationDensity(text) {
    if (!text || text.length === 0) return 0;
    const entropy = this.calculateShannonEntropy(text);
    const redundancy = this.calculateRedundancyRatio(text);

    // Natural English prose / code typically has Shannon entropy between 3.5 and 5.2
    // Max entropy for 256 ASCII is 8.0. Normalizing 0-6 to 0-100 base
    const baseScore = Math.min(100, (entropy / 5.5) * 100);
    const penalizedScore = Math.max(0, baseScore * (1 - redundancy * 0.8));

    return +penalizedScore.toFixed(2);
  }

  compare(rawText, trimmedText) {
    const rawEntropy = this.calculateShannonEntropy(rawText);
    const trimmedEntropy = this.calculateShannonEntropy(trimmedText);

    const rawRedundancy = this.calculateRedundancyRatio(rawText);
    const trimmedRedundancy = this.calculateRedundancyRatio(trimmedText);

    const rawDensity = this.calculateInformationDensity(rawText);
    const trimmedDensity = this.calculateInformationDensity(trimmedText);

    const charsSaved = rawText.length - trimmedText.length;
    const compressionRatio = rawText.length > 0 ? +((charsSaved / rawText.length) * 100).toFixed(2) : 0;
    const densityGainPercent = rawDensity > 0 ? +(((trimmedDensity - rawDensity) / rawDensity) * 100).toFixed(2) : 0;

    return {
      timestamp: new Date().toISOString(),
      rawMetrics: {
        lengthChars: rawText.length,
        shannonEntropy: rawEntropy,
        redundancyRatio: rawRedundancy,
        informationDensityScore: rawDensity
      },
      trimmedMetrics: {
        lengthChars: trimmedText.length,
        shannonEntropy: trimmedEntropy,
        redundancyRatio: trimmedRedundancy,
        informationDensityScore: trimmedDensity
      },
      improvements: {
        charsSaved,
        compressionRatioPercent: compressionRatio,
        redundancyReduction: +(rawRedundancy - trimmedRedundancy).toFixed(4),
        densityGainPercent
      }
    };
  }
}

module.exports = { ContextEntropyMeasurer };
