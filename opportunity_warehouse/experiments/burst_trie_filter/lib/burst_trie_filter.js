/**
 * Context Window Token Dynamic Bounded Fast Succinct Burst Trie Cache Filter
 * Implements a Burst Trie (access trie + dynamic container leaves) that bursts
 * leaf containers into internal trie nodes upon exceeding capacity threshold.
 */

class BurstTrieNode {
  constructor(isLeaf = true, burstThreshold = 4) {
    this.isLeaf = isLeaf;
    this.burstThreshold = burstThreshold;
    this.children = new Map(); // char/token -> BurstTrieNode (if internal)
    this.container = []; // array of { suffix: string, value: any } (if leaf)
  }
}

class BurstTrieFilter {
  constructor(burstThreshold = 3) {
    this.burstThreshold = burstThreshold;
    this.root = new BurstTrieNode(true, this.burstThreshold);
    this.totalEntries = 0;
    this.burstCount = 0;
  }

  insert(key, value) {
    this._insert(this.root, key, 0, value);
    this.totalEntries++;
  }

  _insert(node, key, depth, value) {
    if (node.isLeaf) {
      const suffix = key.slice(depth);
      node.container.push({ suffix, value, originalKey: key });

      if (node.container.length > this.burstThreshold) {
        this._burst(node, depth);
      }
      return;
    }

    const char = depth < key.length ? key[depth] : '$';
    if (!node.children.has(char)) {
      node.children.set(char, new BurstTrieNode(true, this.burstThreshold));
    }
    this._insert(node.children.get(char), key, depth + 1, value);
  }

  _burst(node, depth) {
    this.burstCount++;
    node.isLeaf = false;
    const oldContainer = node.container;
    node.container = [];

    for (const item of oldContainer) {
      const char = item.suffix.length > 0 ? item.suffix[0] : '$';
      if (!node.children.has(char)) {
        node.children.set(char, new BurstTrieNode(true, this.burstThreshold));
      }
      const child = node.children.get(char);
      const remainingSuffix = item.suffix.length > 0 ? item.suffix.slice(1) : '';
      child.container.push({ suffix: remainingSuffix, value: item.value, originalKey: item.originalKey });
    }
  }

  search(key) {
    let curr = this.root;
    let depth = 0;

    while (curr) {
      if (curr.isLeaf) {
        const targetSuffix = key.slice(depth);
        const match = curr.container.find(item => item.suffix === targetSuffix);
        return match ? match.value : null;
      }

      const char = depth < key.length ? key[depth] : '$';
      if (!curr.children.has(char)) return null;
      curr = curr.children.get(char);
      depth++;
    }
    return null;
  }

  getMetrics() {
    return {
      totalEntries: this.totalEntries,
      burstCount: this.burstCount,
      burstThreshold: this.burstThreshold
    };
  }
}

module.exports = { BurstTrieFilter, BurstTrieNode };
