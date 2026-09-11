/**
 * Context Window Token Dynamic Bounded Fast Succinct Ternary Search Tree Filter
 * Implements a Ternary Search Tree (Bentley & Sedgewick 1997) combining
 * memory efficiency with O(L + log N) search and prefix enumeration.
 */

class TSTNode {
  constructor(char) {
    this.char = char;
    this.left = null;   // < char
    this.mid = null;    // == char
    this.right = null;  // > char
    this.value = null;
    this.isEnd = false;
  }
}

class TernarySearchTreeFilter {
  constructor() {
    this.root = null;
    this.size = 0;
  }

  insert(key, value) {
    if (!key || key.length === 0) return;
    this.root = this._insert(this.root, key, 0, value);
  }

  _insert(node, key, index, value) {
    const c = key[index];
    if (!node) {
      node = new TSTNode(c);
    }

    if (c < node.char) {
      node.left = this._insert(node.left, key, index, value);
    } else if (c > node.char) {
      node.right = this._insert(node.right, key, index, value);
    } else {
      if (index + 1 < key.length) {
        node.mid = this._insert(node.mid, key, index + 1, value);
      } else {
        if (!node.isEnd) this.size++;
        node.isEnd = true;
        node.value = value;
      }
    }
    return node;
  }

  search(key) {
    if (!key || key.length === 0) return null;
    const node = this._searchNode(this.root, key, 0);
    return node && node.isEnd ? node.value : null;
  }

  _searchNode(node, key, index) {
    if (!node) return null;
    const c = key[index];

    if (c < node.char) {
      return this._searchNode(node.left, key, index);
    } else if (c > node.char) {
      return this._searchNode(node.right, key, index);
    } else {
      if (index + 1 < key.length) {
        return this._searchNode(node.mid, key, index + 1);
      } else {
        return node;
      }
    }
  }

  keysWithPrefix(prefix) {
    if (!prefix || prefix.length === 0) return [];
    const prefixNode = this._searchNode(this.root, prefix, 0);
    if (!prefixNode) return [];

    const results = [];
    if (prefixNode.isEnd) {
      results.push({ key: prefix, value: prefixNode.value });
    }

    this._collect(prefixNode.mid, prefix, results);
    return results;
  }

  _collect(node, currentPrefix, results) {
    if (!node) return;

    this._collect(node.left, currentPrefix, results);

    const nextPrefix = currentPrefix + node.char;
    if (node.isEnd) {
      results.push({ key: nextPrefix, value: node.value });
    }
    this._collect(node.mid, nextPrefix, results);

    this._collect(node.right, currentPrefix, results);
  }

  getMetrics() {
    return {
      storedKeys: this.size,
      hasRoot: this.root !== null
    };
  }
}

module.exports = { TernarySearchTreeFilter, TSTNode };
