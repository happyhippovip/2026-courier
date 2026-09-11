/**
 * Hierarchical Trie-Based Inverted Index & Token Proximity Ranker
 * Indexes multi-document token streams with exact character trie nodes
 * and maintains positional posting lists for sub-millisecond proximity queries.
 */

class TrieNode {
  constructor() {
    this.children = new Map();
    this.postings = new Map(); // docId -> Array of positions
    this.isTerminal = false;
  }
}

class TrieInvertedIndex {
  constructor() {
    this.root = new TrieNode();
    this.docLengths = new Map();
  }

  // Index a token sequence for a given docId
  indexDocument(docId, tokens) {
    this.docLengths.set(docId, tokens.length);

    for (let pos = 0; pos < tokens.length; pos++) {
      const token = tokens[pos].toLowerCase();
      let node = this.root;

      for (let i = 0; i < token.length; i++) {
        const char = token[i];
        if (!node.children.has(char)) {
          node.children.set(char, new TrieNode());
        }
        node = node.children.get(char);
      }

      node.isTerminal = true;
      if (!node.postings.has(docId)) {
        node.postings.set(docId, []);
      }
      node.postings.get(docId).push(pos);
    }
  }

  // Find exact posting list for a given token
  getPostings(token) {
    const normalized = token.toLowerCase();
    let node = this.root;

    for (let i = 0; i < normalized.length; i++) {
      const char = normalized[i];
      if (!node.children.has(char)) {
        return null;
      }
      node = node.children.get(char);
    }

    return node.isTerminal ? node.postings : null;
  }

  // Search for two tokens occurring within maxDistance of each other
  searchProximity(tokenA, tokenB, maxDistance = 2) {
    const postingsA = this.getPostings(tokenA);
    const postingsB = this.getPostings(tokenB);

    if (!postingsA || !postingsB) return [];

    const commonDocs = [];
    for (const docId of postingsA.keys()) {
      if (postingsB.has(docId)) {
        const posA = postingsA.get(docId);
        const posB = postingsB.get(docId);

        let minDiff = Infinity;
        let matchedPairs = [];

        for (const pA of posA) {
          for (const pB of posB) {
            const diff = Math.abs(pA - pB);
            if (diff <= maxDistance && diff > 0) {
              matchedPairs.push({ posA: pA, posB: pB, distance: diff });
              if (diff < minDiff) minDiff = diff;
            }
          }
        }

        if (matchedPairs.length > 0) {
          commonDocs.push({
            docId,
            minDistance: minDiff,
            matches: matchedPairs
          });
        }
      }
    }

    commonDocs.sort((a, b) => a.minDistance - b.minDistance);
    return commonDocs;
  }
}

module.exports = { TrieInvertedIndex, TrieNode };
