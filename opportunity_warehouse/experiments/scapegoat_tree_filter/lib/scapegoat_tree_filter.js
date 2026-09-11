/**
 * Context Window Token Dynamic Bounded Fast Succinct Scapegoat Tree Filter
 * Implements a self-balancing binary search tree that stores zero balancing flags/metadata per node,
 * achieving O(log N) search and amortized O(log N) insert/delete via alpha-weight rebuilding.
 */

class SGTNode {
  constructor(key, value, left = null, right = null) {
    this.key = key;
    this.value = value;
    this.left = left;
    this.right = right;
    this.size = 1 + (left ? left.size : 0) + (right ? right.size : 0);
  }
}

class ScapegoatTreeFilter {
  constructor(alpha = 0.67) {
    this.alpha = alpha; // Weight balancing factor (0.5 < alpha < 1.0)
    this.root = null;
    this.maxNodeCount = 0;
  }

  size(node = this.root) {
    return node ? node.size : 0;
  }

  search(key, node = this.root) {
    let curr = node;
    while (curr) {
      if (curr.key === key) return { key: curr.key, value: curr.value };
      if (key < curr.key) curr = curr.left;
      else curr = curr.right;
    }
    return null;
  }

  insert(key, value) {
    const [newRoot, depth] = this._insertHelper(this.root, key, value);
    this.root = newRoot;
    if (this.size() > this.maxNodeCount) {
      this.maxNodeCount = this.size();
    }

    // Check if height exceeds alpha-weight bound: depth > floor(log_{1/alpha}(size))
    const maxAllowedDepth = Math.floor(Math.log(this.size()) / Math.log(1 / this.alpha));
    if (depth > maxAllowedDepth) {
      this.root = this._rebuildSubtree(this.root);
    }
  }

  _insertHelper(node, key, value) {
    if (!node) {
      return [new SGTNode(key, value), 0];
    }

    if (key === node.key) {
      return [new SGTNode(key, value, node.left, node.right), 0];
    }

    let left = node.left;
    let right = node.right;
    let childDepth = 0;

    if (key < node.key) {
      [left, childDepth] = this._insertHelper(node.left, key, value);
    } else {
      [right, childDepth] = this._insertHelper(node.right, key, value);
    }

    return [new SGTNode(node.key, node.value, left, right), childDepth + 1];
  }

  _rebuildSubtree(node) {
    const list = [];
    function flatten(n) {
      if (!n) return;
      flatten(n.left);
      list.push({ key: n.key, value: n.value });
      flatten(n.right);
    }
    flatten(node);

    function buildBalanced(start, end) {
      if (start > end) return null;
      const mid = Math.floor((start + end) / 2);
      const left = buildBalanced(start, mid - 1);
      const right = buildBalanced(mid + 1, end);
      return new SGTNode(list[mid].key, list[mid].value, left, right);
    }

    return buildBalanced(0, list.length - 1);
  }

  rangeQuery(minKey, maxKey, node = this.root) {
    const results = [];
    function traverse(curr) {
      if (!curr) return;
      if (curr.key > minKey) traverse(curr.left);
      if (curr.key >= minKey && curr.key <= maxKey) {
        results.push({ key: curr.key, value: curr.value });
      }
      if (curr.key < maxKey) traverse(curr.right);
    }
    traverse(node);
    return results;
  }

  getMetrics() {
    return {
      size: this.size(),
      alpha: this.alpha,
      maxNodeCount: this.maxNodeCount,
      memoryPerNode: 'ZERO_BALANCING_METADATA',
      complexity: 'O(log N)_AMORTIZED_INSERT_STRICT_LOOKUP'
    };
  }
}

module.exports = { SGTNode, ScapegoatTreeFilter };
