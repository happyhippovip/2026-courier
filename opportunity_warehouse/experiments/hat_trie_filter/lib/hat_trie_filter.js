/**
 * Context Window Token Dynamic Bounded Fast Succinct HAT-Trie Cache Filter
 * Implements a HAT-Trie (Hash-Array Mapped Trie hybrid) where internal nodes
 * act as an access trie and leaf nodes maintain cache-friendly hash tables that
 * burst into trie branches upon exceeding bucket capacity.
 */

class HATHashBucket {
  constructor(capacity = 4) {
    this.capacity = capacity;
    this.map = new Map(); // suffix -> { originalKey, value }
  }

  insert(suffix, originalKey, value) {
    this.map.set(suffix, { originalKey, value });
    return this.map.size > this.capacity;
  }

  get(suffix) {
    const item = this.map.get(suffix);
    return item ? item.value : null;
  }

  entries() {
    return Array.from(this.map.entries());
  }
}

class HATTrieNode {
  constructor(isLeaf = true, bucketCapacity = 4) {
    this.isLeaf = isLeaf;
    this.bucketCapacity = bucketCapacity;
    this.children = new Map(); // char -> HATTrieNode
    this.bucket = isLeaf ? new HATHashBucket(bucketCapacity) : null;
  }
}

class HATTrieFilter {
  constructor(bucketCapacity = 3) {
    this.bucketCapacity = bucketCapacity;
    this.root = new HATTrieNode(true, this.bucketCapacity);
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
      const shouldBurst = node.bucket.insert(suffix, key, value);

      if (shouldBurst) {
        this._burst(node, depth);
      }
      return;
    }

    const char = depth < key.length ? key[depth] : '$';
    if (!node.children.has(char)) {
      node.children.set(char, new HATTrieNode(true, this.bucketCapacity));
    }
    this._insert(node.children.get(char), key, depth + 1, value);
  }

  _burst(node, depth) {
    this.burstCount++;
    node.isLeaf = false;
    const oldEntries = node.bucket.entries();
    node.bucket = null;

    for (const [suffix, data] of oldEntries) {
      const char = suffix.length > 0 ? suffix[0] : '$';
      if (!node.children.has(char)) {
        node.children.set(char, new HATTrieNode(true, this.bucketCapacity));
      }
      const child = node.children.get(char);
      const remainingSuffix = suffix.length > 0 ? suffix.slice(1) : '';
      child.bucket.insert(remainingSuffix, data.originalKey, data.value);
    }
  }

  search(key) {
    let curr = this.root;
    let depth = 0;

    while (curr) {
      if (curr.isLeaf) {
        const suffix = key.slice(depth);
        return curr.bucket.get(suffix);
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
      bucketCapacity: this.bucketCapacity
    };
  }
}

module.exports = { HATTrieFilter, HATTrieNode, HATHashBucket };
