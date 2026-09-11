/**
 * Context Window Streaming Token Entropy Anomaly Detector & Perplexity Guard
 * Computes sliding-window Shannon entropy over streaming agent generation buffers,
 * detecting degenerate repetitive loops (near-zero entropy) and corrupted binary noise (spurious high entropy).
 */

class TokenEntropyGuard {
  constructor(options = {}) {
    this.windowSize = options.windowSize || 40; // sliding character window
    this.lowEntropyThreshold = options.lowEntropyThreshold || 2.8; // loop threshold
    this.highEntropyThreshold = options.highEntropyThreshold || 5.2; // noise threshold
  }

  computeShannonEntropy(text) {
    if (!text || text.length === 0) return 0;
    const len = text.length;
    const freqs = new Map();
    for (let i = 0; i < len; i++) {
      const ch = text[i];
      freqs.set(ch, (freqs.get(ch) || 0) + 1);
    }

    let entropy = 0;
    for (const count of freqs.values()) {
      const p = count / len;
      entropy -= p * Math.log2(p);
    }
    return Number(entropy.toFixed(4));
  }

  evaluateWindow(text) {
    const entropy = this.computeShannonEntropy(text);
    let status = 'NORMAL';
    if (entropy < this.lowEntropyThreshold) {
      status = 'ANOMALY_LOW_ENTROPY'; // repetitive loop
    } else if (entropy > this.highEntropyThreshold) {
      status = 'ANOMALY_HIGH_ENTROPY'; // random/binary corruption
    }

    return {
      textLength: text.length,
      entropy,
      status,
      isLoop: status === 'ANOMALY_LOW_ENTROPY',
      isNoise: status === 'ANOMALY_HIGH_ENTROPY'
    };
  }

  evaluateStream(chunks) {
    const fullText = Array.isArray(chunks) ? chunks.join('') : chunks;
    const results = [];
    let loopDetectedCount = 0;
    let noiseDetectedCount = 0;

    const step = Math.max(10, Math.floor(this.windowSize / 2));
    for (let i = 0; i <= fullText.length - this.windowSize; i += step) {
      const windowText = fullText.substring(i, i + this.windowSize);
      const evalRes = this.evaluateWindow(windowText);
      evalRes.offset = i;
      results.push(evalRes);

      if (evalRes.isLoop) loopDetectedCount++;
      if (evalRes.isNoise) noiseDetectedCount++;
    }

    const haltRecommended = loopDetectedCount >= 2 || noiseDetectedCount >= 2;

    return {
      totalLength: fullText.length,
      windowsEvaluated: results.length,
      loopDetectedCount,
      noiseDetectedCount,
      haltRecommended,
      windows: results
    };
  }
}

module.exports = { TokenEntropyGuard };
