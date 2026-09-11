/**
 * Context Window Token Dynamic Bounded Fast Succinct Persistent Suffix Tree Filter
 * Compressed trie indexing all suffixes of a token stream.
 * Enables exact pattern search in O(M) time and repeated substring discovery.
 */

class SuffixTreeNode {
  constructor(start = -1, end = -1) {
    this.start = start;
    this.end = end;
    this.children = new Map(); // token -> SuffixTreeNode
    this.suffixIndices = [];
  }
}

class PersistentSuffixTreeFilter {
  constructor() {
    this.root = new SuffixTreeNode();
    this.tokens = [];
  }

  build(tokens) {
    this.tokens = Array.from(tokens);
    this.root = new SuffixTreeNode();
    const n = this.tokens.length;

    for (let i = 0; i < n; i++) {
      this._insertSuffix(i);
    }
  }

  _insertSuffix(suffixIndex) {
    let curr = this.root;
    curr.suffixIndices.push(suffixIndex);

    for (let i = suffixIndex; i < this.tokens.length; i++) {
      const tok = this.tokens[i];
      if (!curr.children.has(tok)) {
        curr.children.set(tok, new SuffixTreeNode(i, this.tokens.length - 1));
      }
      curr = curr.children.get(tok);
      curr.suffixIndices.push(suffixIndex);
    }
  }

  search(pattern) {
    if (!pattern || pattern.length === 0) return { found: false, occurrences: 0, indices: [] };
    let curr = this.root;

    for (let i = 0; i < pattern.length; i++) {
      const tok = pattern[i];
      if (!curr.children.has(tok)) {
        return { found: false, occurrences: 0, indices: [] };
      }
      curr = curr.children.get(tok);
    }

    // Filter indices to ensure exact match of full pattern
    const matchedIndices = curr.suffixIndices.filter(startIdx => {
      if (startIdx + pattern.length > this.tokens.length) return false;
      for (let j = 0; j < pattern.length; j++) {
        if (this.tokens[startIdx + j] !== pattern[j]) return false;
      }
      return true;
    });

    const uniqueIndices = Array.from(new Set(matchedIndices)).sort((a, b) => a - b);

    return {
      found: uniqueIndices.length > 0,
      occurrences: uniqueIndices.length,
      indices: uniqueIndices
    };
  }

  findLongestRepeatedSequence(minLen = 2) {
    let best = [];

    const traverse = (node, path) => {
      if (node.suffixIndices.length >= 2 && path.length >= minLen) {
        if (path.length > best.length) {
          best = [...path];
        }
      }
      for (const [tok, child] of node.children.entries()) {
        traverse(child, [...path, tok]);
      }
    };

    traverse(this.root, []);
    return best;
  }
}

module.exports = { PersistentSuffixTreeFilter, SuffixTreeNode };
