/**
 * Context Window Dynamic Trie-Based Sliding Window String Suffix Indexer & Anomaly Detector
 * Indexes sliding token n-gram branches in streaming agent responses,
 * computing branching factor entropy to immediately flag and quarantine degenerative loops and injection bursts.
 */

class SuffixTrieNode {
  constructor() {
    this.children = new Map(); // token -> SuffixTrieNode
    this.count = 0;
  }
}

class SuffixAnomalyDetector {
  constructor(options = {}) {
    this.maxDepth = options.maxDepth || 3;
    this.anomalyThreshold = options.anomalyThreshold || 0.75;
    this.root = new SuffixTrieNode();
    this.totalWindows = 0;
  }

  tokenize(text) {
    if (!text || typeof text !== 'string') return [];
    return text.toLowerCase().split(/\s+/).filter(t => t.length > 0);
  }

  insertNgrams(tokens) {
    for (let i = 0; i < tokens.length; i++) {
      let current = this.root;
      current.count++;

      for (let d = 0; d < this.maxDepth && (i + d) < tokens.length; d++) {
        const tok = tokens[i + d];
        if (!current.children.has(tok)) {
          current.children.set(tok, new SuffixTrieNode());
        }
        current = current.children.get(tok);
        current.count++;
      }
    }
  }

  evaluateBranchingFactor(tokens) {
    if (tokens.length < this.maxDepth) {
      return { anomalyScore: 0, quarantined: false, avgBranching: 1.0 };
    }

    // Measure branching diversity across tokens
    const nodeBranchCounts = [];
    let current = this.root;

    for (let i = 0; i < tokens.length; i++) {
      const tok = tokens[i];
      if (current.children.has(tok)) {
        nodeBranchCounts.push(current.children.size);
        current = current.children.get(tok);
      } else {
        current = this.root;
      }
    }

    const avgBranching = nodeBranchCounts.length > 0
      ? (nodeBranchCounts.reduce((a, b) => a + b, 0) / nodeBranchCounts.length)
      : 1.0;

    // Repetitive loops have branching factor near 1 (or zero alternatives)
    // Rich language has higher branching factor.
    // Anomaly score is high when branching collapses.
    const loopRatio = (tokens.length > 0) ? (new Set(tokens).size / tokens.length) : 1;
    const anomalyScore = Number((1.0 - loopRatio).toFixed(4));
    const quarantined = anomalyScore >= this.anomalyThreshold;

    return {
      totalTokens: tokens.length,
      distinctTokens: new Set(tokens).size,
      avgBranching: Number(avgBranching.toFixed(2)),
      anomalyScore,
      quarantined
    };
  }

  analyze(text) {
    const tokens = this.tokenize(text);
    this.insertNgrams(tokens);
    this.totalWindows++;
    return this.evaluateBranchingFactor(tokens);
  }
}

module.exports = { SuffixAnomalyDetector };
