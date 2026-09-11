/**
 * Semantic Prompt Information Bottleneck & Mutual Information Estimator
 * Implements information-theoretic scoring to balance context compression
 * with task-objective mutual information retention.
 */

class InformationBottleneckEstimator {
  constructor(options = {}) {
    this.tradeoffBeta = options.tradeoffBeta || 1.8; // importance of task relevance vs brevity
    this.stopWords = new Set(['and', 'or', 'the', 'a', 'an', 'in', 'on', 'of', 'to', 'for', 'with', 'at', 'by', 'from', 'is', 'are', 'was', 'were', 'it', 'this', 'that']);
  }

  calculateEntropy(text = '') {
    if (!text || text.length === 0) return 0;
    const freq = {};
    for (const char of text) {
      freq[char] = (freq[char] || 0) + 1;
    }

    const total = text.length;
    let entropy = 0;
    for (const count of Object.values(freq)) {
      const p = count / total;
      entropy -= p * Math.log2(p);
    }
    return Number(entropy.toFixed(3));
  }

  calculateTaskRelevance(sectionText = '', targetObjective = '') {
    if (!sectionText || !targetObjective) return 0;

    const tokenize = str => str
      .toLowerCase()
      .replace(/[^a-z0-9_]/g, ' ')
      .split(/\s+/)
      .filter(w => w.length > 1 && !this.stopWords.has(w));

    const objectiveWords = new Set(tokenize(targetObjective));
    const sectionWords = tokenize(sectionText);

    if (objectiveWords.size === 0 || sectionWords.length === 0) return 0;

    let matchCount = 0;
    for (const w of sectionWords) {
      if (objectiveWords.has(w)) matchCount++;
    }

    // Normalized relevance score [0, 1]
    const relevance = Math.min(1.0, (matchCount / Math.sqrt(sectionWords.length * objectiveWords.size)) * 2);
    return Number(relevance.toFixed(3));
  }

  evaluateBottleneck(sections = [], targetObjective = '') {
    const evaluated = sections.map(s => {
      const entropy = this.calculateEntropy(s.content);
      const relevance = this.calculateTaskRelevance(s.content, targetObjective);
      const tokens = s.tokens || Math.round((s.content || '').length / 4);

      // Objective function: Maximize Relevance, Minimize Token Cost
      const objectiveScore = Number(((relevance * this.tradeoffBeta) - (tokens / 2000)).toFixed(3));

      return {
        id: s.id,
        label: s.label || s.id,
        tokens,
        entropy,
        relevance,
        objectiveScore,
        retainRecommendation: objectiveScore > 0.1 || relevance > 0.4
      };
    });

    // Sort by objectiveScore descending
    evaluated.sort((a, b) => b.objectiveScore - a.objectiveScore);

    const retained = evaluated.filter(e => e.retainRecommendation);
    const prunable = evaluated.filter(e => !e.retainRecommendation);

    const originalTokens = evaluated.reduce((acc, e) => acc + e.tokens, 0);
    const retainedTokens = retained.reduce((acc, e) => acc + e.tokens, 0);
    const prunedTokens = prunable.reduce((acc, e) => acc + e.tokens, 0);

    return {
      targetObjective,
      tradeoffBeta: this.tradeoffBeta,
      originalTokens,
      retainedTokens,
      prunedTokens,
      tokenReductionPercent: originalTokens > 0 ? Number(((prunedTokens / originalTokens) * 100).toFixed(1)) : 0,
      evaluatedSections: evaluated
    };
  }
}

module.exports = { InformationBottleneckEstimator };
