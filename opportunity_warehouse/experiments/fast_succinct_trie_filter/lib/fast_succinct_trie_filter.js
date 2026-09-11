/**
 * Fast Succinct Trie (FST) Filter with Level-Order Unary Degree Sequence (LOUDS)
 * Provides O(k) exact match and longest-prefix lookup for tokenized context window streams
 * with minimal bitvector overhead and high compression ratio over pointer tries.
 */

class FastSuccinctTrieBuilder {
  constructor() {
    this.root = { children: new Map(), isTerminal: false, value: null };
    this.keyCount = 0;
  }

  insert(key, value = null) {
    if (typeof key !== 'string' || key.length === 0) return;
    let curr = this.root;
    for (let i = 0; i < key.length; i++) {
      const char = key[i];
      if (!curr.children.has(char)) {
        curr.children.set(char, { children: new Map(), isTerminal: false, value: null });
      }
      curr = curr.children.get(char);
    }
    curr.isTerminal = true;
    curr.value = value !== null ? value : key;
    this.keyCount++;
  }

  build() {
    // Level-Order Unary Degree Sequence (LOUDS) encoding
    // Super-root node 0 has 1 child: node 1 (root) -> louds begins with 1, 0
    // We use 1-based indexing for nodes where root is node 1
    const louds = [1, 0];
    const labels = ['\0', '\0']; // labels[0] dummy, labels[1] root
    const terminals = [0, this.root.isTerminal ? 1 : 0];
    const values = [null, this.root.value];

    const queue = [this.root];
    let nodeCount = 1;

    while (queue.length > 0) {
      const curr = queue.shift();
      const sortedKeys = Array.from(curr.children.keys()).sort();
      for (const char of sortedKeys) {
        const child = curr.children.get(char);
        louds.push(1);
        labels.push(char);
        terminals.push(child.isTerminal ? 1 : 0);
        values.push(child.value);
        queue.push(child);
        nodeCount++;
      }
      louds.push(0); // delimiter for degree of curr
    }

    return new FastSuccinctTrie(louds, labels, terminals, values, nodeCount, this.keyCount);
  }
}

class FastSuccinctTrie {
  constructor(louds, labels, terminals, values, nodeCount, keyCount) {
    this.louds = louds;
    this.labels = labels;
    this.terminals = terminals;
    this.values = values;
    this.nodeCount = nodeCount;
    this.keyCount = keyCount;

    this._buildRankSelectTables();
  }

  _buildRankSelectTables() {
    const n = this.louds.length;
    this.rank1Table = new Int32Array(n);
    this.select0Table = [-1]; // 1-based indexing

    let r1 = 0;
    for (let i = 0; i < n; i++) {
      if (this.louds[i] === 1) {
        r1++;
      } else {
        this.select0Table.push(i);
      }
      this.rank1Table[i] = r1;
    }
  }

  rank1(idx) {
    if (idx < 0) return 0;
    if (idx >= this.rank1Table.length) return this.rank1Table[this.rank1Table.length - 1];
    return this.rank1Table[idx];
  }

  select0(k) {
    if (k <= 0 || k >= this.select0Table.length) return -1;
    return this.select0Table[k];
  }

  exactMatch(key) {
    if (typeof key !== 'string') return { found: false, value: null };
    let currNode = 1; // root is node 1

    for (let i = 0; i < key.length; i++) {
      const targetChar = key[i];
      const start0 = this.select0(currNode);
      const next0 = this.select0(currNode + 1);
      if (start0 === -1 || next0 === -1) return { found: false, value: null };

      let foundNode = -1;
      for (let pos = start0 + 1; pos <= next0 - 1; pos++) {
        const childNode = this.rank1(pos);
        if (this.labels[childNode] === targetChar) {
          foundNode = childNode;
          break;
        }
      }

      if (foundNode === -1) {
        return { found: false, value: null };
      }

      currNode = foundNode;
    }

    const isTerminal = this.terminals[currNode] === 1;
    return {
      found: isTerminal,
      value: isTerminal ? this.values[currNode] : null,
      nodeIndex: currNode
    };
  }

  longestPrefixMatch(text) {
    if (typeof text !== 'string') return { match: null, length: 0, value: null };
    let currNode = 1;
    let bestMatch = null;
    let bestLen = 0;
    let bestVal = null;

    if (this.terminals[currNode] === 1) {
      bestLen = 0;
      bestVal = this.values[currNode];
      bestMatch = '';
    }

    for (let i = 0; i < text.length; i++) {
      const targetChar = text[i];
      const start0 = this.select0(currNode);
      const next0 = this.select0(currNode + 1);
      if (start0 === -1 || next0 === -1) break;

      let foundNode = -1;
      for (let pos = start0 + 1; pos <= next0 - 1; pos++) {
        const childNode = this.rank1(pos);
        if (this.labels[childNode] === targetChar) {
          foundNode = childNode;
          break;
        }
      }

      if (foundNode === -1) break;

      currNode = foundNode;
      if (this.terminals[currNode] === 1) {
        bestLen = i + 1;
        bestMatch = text.slice(0, bestLen);
        bestVal = this.values[currNode];
      }
    }

    return {
      match: bestMatch,
      length: bestLen,
      value: bestVal
    };
  }

  hasPrefix(prefix) {
    if (typeof prefix !== 'string') return false;
    let currNode = 1;

    for (let i = 0; i < prefix.length; i++) {
      const targetChar = prefix[i];
      const start0 = this.select0(currNode);
      const next0 = this.select0(currNode + 1);
      if (start0 === -1 || next0 === -1) return false;

      let foundNode = -1;
      for (let pos = start0 + 1; pos <= next0 - 1; pos++) {
        const childNode = this.rank1(pos);
        if (this.labels[childNode] === targetChar) {
          foundNode = childNode;
          break;
        }
      }

      if (foundNode === -1) return false;
      currNode = foundNode;
    }
    return true;
  }

  getMetrics() {
    const loudsBytes = Math.ceil(this.louds.length / 8);
    const labelBytes = this.labels.length;
    const terminalBytes = Math.ceil(this.terminals.length / 8);
    const succinctBytes = loudsBytes + labelBytes + terminalBytes;
    const pointerTrieEstimatedBytes = this.nodeCount * 48; // estimated ~48 bytes per JS node/Map edge
    const compressionRatio = pointerTrieEstimatedBytes > 0 
      ? (1 - (succinctBytes / pointerTrieEstimatedBytes)).toFixed(4)
      : '0.0000';

    return {
      nodeCount: this.nodeCount,
      keyCount: this.keyCount,
      loudsBits: this.louds.length,
      succinctBytes,
      pointerTrieEstimatedBytes,
      compressionRatio: parseFloat(compressionRatio),
      savingsPercent: (parseFloat(compressionRatio) * 100).toFixed(2) + '%'
    };
  }
}

module.exports = { FastSuccinctTrieBuilder, FastSuccinctTrie };
