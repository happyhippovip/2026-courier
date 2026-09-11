/**
 * Context Window Variable-Order Markov Transition Predictor & Speculative Token Pre-Fetcher
 * Estimates n-gram transition probabilities over historical context buffer streams
 * to speculatively pre-warm KV-cache allocations and accelerate multi-agent turn generation.
 */

class MarkovTokenPrefetcher {
  constructor(options = {}) {
    this.maxOrder = options.maxOrder || 2; // Supports unigram, bigram, trigram
    this.unigramCounts = {};
    this.bigramCounts = {};
    this.trigramCounts = {};
    this.totalTokens = 0;
  }

  tokenize(text) {
    if (!text || typeof text !== 'string') return [];
    return text
      .toLowerCase()
      .replace(/[^a-z0-9_\s]/g, ' ')
      .split(/\s+/)
      .filter(t => t.length > 0);
  }

  train(corpus) {
    const textList = Array.isArray(corpus) ? corpus : [corpus];
    for (const text of textList) {
      const tokens = this.tokenize(text);
      for (let i = 0; i < tokens.length; i++) {
        const t0 = tokens[i];
        this.totalTokens++;
        this.unigramCounts[t0] = (this.unigramCounts[t0] || 0) + 1;

        if (i > 0) {
          const tPrev = tokens[i - 1];
          if (!this.bigramCounts[tPrev]) {
            this.bigramCounts[tPrev] = { total: 0, next: {} };
          }
          this.bigramCounts[tPrev].total++;
          this.bigramCounts[tPrev].next[t0] = (this.bigramCounts[tPrev].next[t0] || 0) + 1;
        }

        if (i > 1) {
          const tPrev2 = tokens[i - 2] + ' ' + tokens[i - 1];
          if (!this.trigramCounts[tPrev2]) {
            this.trigramCounts[tPrev2] = { total: 0, next: {} };
          }
          this.trigramCounts[tPrev2].total++;
          this.trigramCounts[tPrev2].next[t0] = (this.trigramCounts[tPrev2].next[t0] || 0) + 1;
        }
      }
    }
  }

  predictNext(tokens, topK = 3) {
    const tokenList = Array.isArray(tokens) ? tokens : this.tokenize(tokens);
    const n = tokenList.length;

    // Try trigram context first (if n >= 2)
    if (this.maxOrder >= 2 && n >= 2) {
      const ctx2 = tokenList[n - 2] + ' ' + tokenList[n - 1];
      if (this.trigramCounts[ctx2] && this.trigramCounts[ctx2].total > 0) {
        return this.rankPredictions(this.trigramCounts[ctx2], topK, 'trigram');
      }
    }

    // Try bigram context (if n >= 1)
    if (this.maxOrder >= 1 && n >= 1) {
      const ctx1 = tokenList[n - 1];
      if (this.bigramCounts[ctx1] && this.bigramCounts[ctx1].total > 0) {
        return this.rankPredictions(this.bigramCounts[ctx1], topK, 'bigram');
      }
    }

    // Fallback to unigrams
    const unigramEntries = Object.entries(this.unigramCounts)
      .map(([token, count]) => ({
        token,
        probability: this.totalTokens > 0 ? (count / this.totalTokens) : 0,
        order: 'unigram'
      }))
      .sort((a, b) => b.probability - a.probability)
      .slice(0, topK);

    return unigramEntries;
  }

  rankPredictions(bucket, topK, order) {
    return Object.entries(bucket.next)
      .map(([token, count]) => ({
        token,
        probability: Number((count / bucket.total).toFixed(4)),
        order
      }))
      .sort((a, b) => b.probability - a.probability)
      .slice(0, topK);
  }

  speculativePrefetch(prefixText, horizon = 3) {
    const tokens = this.tokenize(prefixText);
    const prefetched = [];
    const workingTokens = [...tokens];

    for (let step = 0; step < horizon; step++) {
      const preds = this.predictNext(workingTokens, 1);
      if (preds.length === 0) break;
      const best = preds[0];
      prefetched.push({
        step: step + 1,
        token: best.token,
        probability: best.probability,
        order: best.order
      });
      workingTokens.push(best.token);
    }

    const avgConfidence = prefetched.length > 0
      ? prefetched.reduce((acc, p) => acc + p.probability, 0) / prefetched.length
      : 0;

    return {
      prefix: prefixText,
      horizon,
      prefetchedSequence: prefetched.map(p => p.token).join(' '),
      prefetchedTokens: prefetched,
      meanConfidence: Number(avgConfidence.toFixed(4))
    };
  }

  evaluateAccuracy(testText, topK = 3) {
    const tokens = this.tokenize(testText);
    if (tokens.length < 2) return { hitRate: 0, evaluatedTransitions: 0 };

    let hits = 0;
    let total = 0;

    for (let i = 1; i < tokens.length; i++) {
      const history = tokens.slice(0, i);
      const target = tokens[i];
      const preds = this.predictNext(history, topK);
      const matched = preds.some(p => p.token === target);
      if (matched) hits++;
      total++;
    }

    return {
      hitRate: Number((hits / total).toFixed(4)),
      hits,
      evaluatedTransitions: total,
      topK
    };
  }
}

module.exports = { MarkovTokenPrefetcher };
