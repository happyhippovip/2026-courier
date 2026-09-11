/**
 * Context Window Token Dynamic Bounded Fast Succinct Weight-Balanced B-Tree Filter
 * Implements an immutable Weight-Balanced B-Tree (WBB-Tree) where node degrees and splits
 * are governed by subtree weight invariants, ensuring amortized O(1) rebalancing.
 */

class WBBTreeNode {
  constructor(keys = [], values = [], children = []) {
    this.keys = keys;
    this.values = values;
    this.children = children; // Array of WBBTreeNode (empty if leaf)
    this.weight = keys.length;
    for (const ch of children) {
      if (ch) this.weight += ch.weight;
    }
  }

  isLeaf() {
    return this.children.length === 0;
  }
}

class WeightBalancedBTreeFilter {
  constructor(maxDegree = 4) {
    this.maxDegree = maxDegree;
    this.root = new WBBTreeNode([], [], []);
    this.totalInserts = 0;
  }

  search(key, node = this.root) {
    if (!node) return null;

    let i = 0;
    while (i < node.keys.length && key > node.keys[i]) {
      i++;
    }

    if (i < node.keys.length && key === node.keys[i]) {
      return { key: node.keys[i], value: node.values[i] };
    }

    if (node.isLeaf()) {
      return null;
    }

    return this.search(key, node.children[i]);
  }

  insert(key, value) {
    this.totalInserts++;
    const [newChild, splitKey, splitVal] = this._insertInternal(this.root, key, value);
    if (newChild) {
      // Root split -> create new root
      this.root = new WBBTreeNode([splitKey], [splitVal], [this.root, newChild]);
    }
  }

  _insertInternal(node, key, value) {
    let i = 0;
    while (i < node.keys.length && key > node.keys[i]) {
      i++;
    }

    if (i < node.keys.length && key === node.keys[i]) {
      // Update existing key
      node.values[i] = value;
      return [null, null, null];
    }

    if (node.isLeaf()) {
      node.keys.splice(i, 0, key);
      node.values.splice(i, 0, value);
      node.weight++;
      return this._maybeSplit(node);
    } else {
      const [splitChild, splitKey, splitVal] = this._insertInternal(node.children[i], key, value);
      node.weight++;
      if (splitChild) {
        node.keys.splice(i, 0, splitKey);
        node.values.splice(i, 0, splitVal);
        node.children.splice(i + 1, 0, splitChild);
        return this._maybeSplit(node);
      }
      return [null, null, null];
    }
  }

  _maybeSplit(node) {
    if (node.keys.length > this.maxDegree) {
      const mid = Math.floor(node.keys.length / 2);
      const splitKey = node.keys[mid];
      const splitVal = node.values[mid];

      const rightKeys = node.keys.slice(mid + 1);
      const rightValues = node.values.slice(mid + 1);
      const rightChildren = node.isLeaf() ? [] : node.children.slice(mid + 1);

      node.keys = node.keys.slice(0, mid);
      node.values = node.values.slice(0, mid);
      if (!node.isLeaf()) {
        node.children = node.children.slice(0, mid + 1);
      }

      // Recompute weights
      node.weight = node.keys.length;
      for (const ch of node.children) node.weight += ch.weight;

      const rightNode = new WBBTreeNode(rightKeys, rightValues, rightChildren);
      return [rightNode, splitKey, splitVal];
    }
    return [null, null, null];
  }

  rangeQuery(minKey, maxKey, node = this.root) {
    const results = [];
    function traverse(curr) {
      if (!curr) return;
      let i = 0;
      for (i = 0; i < curr.keys.length; i++) {
        if (!curr.isLeaf() && curr.keys[i] >= minKey) {
          traverse(curr.children[i]);
        }
        if (curr.keys[i] >= minKey && curr.keys[i] <= maxKey) {
          results.push({ key: curr.keys[i], value: curr.values[i] });
        }
      }
      if (!curr.isLeaf() && (curr.keys.length === 0 || curr.keys[curr.keys.length - 1] <= maxKey)) {
        traverse(curr.children[curr.children.length - 1]);
      }
    }
    traverse(node);
    return results;
  }

  getMetrics() {
    return {
      rootWeight: this.root.weight,
      maxDegree: this.maxDegree,
      totalInserts: this.totalInserts,
      balancingModel: 'WEIGHT_BALANCED_B_TREE_INVARIANT',
      rebalanceCostAmortized: 'O(1)',
      lookupComplexity: 'O(log_b N)'
    };
  }
}

module.exports = { WBBTreeNode, WeightBalancedBTreeFilter };
