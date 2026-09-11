/**
 * Context Window Token Dynamic Interval Tree
 * Augmented Binary Search Tree (AVL balanced) for sub-millisecond range overlap queries
 * over token interval spans [start, end) in multi-turn LLM context memory.
 */

class IntervalNode {
  constructor(low, high, payload) {
    this.low = low;
    this.high = high;
    this.payload = payload;
    this.maxHigh = high;
    this.height = 1;
    this.left = null;
    this.right = null;
  }
}

class IntervalTreeFilter {
  constructor() {
    this.root = null;
    this.size = 0;
  }

  _getHeight(node) {
    return node ? node.height : 0;
  }

  _getMaxHigh(node) {
    return node ? node.maxHigh : -Infinity;
  }

  _update(node) {
    if (!node) return;
    node.height = 1 + Math.max(this._getHeight(node.left), this._getHeight(node.right));
    node.maxHigh = Math.max(
      node.high,
      this._getMaxHigh(node.left),
      this._getMaxHigh(node.right)
    );
  }

  _rotateRight(y) {
    const x = y.left;
    const T2 = x.right;

    x.right = y;
    y.left = T2;

    this._update(y);
    this._update(x);
    return x;
  }

  _rotateLeft(x) {
    const y = x.right;
    const T2 = y.left;

    y.left = x;
    x.right = T2;

    this._update(x);
    this._update(y);
    return y;
  }

  _getBalance(node) {
    return node ? this._getHeight(node.left) - this._getHeight(node.right) : 0;
  }

  insert(low, high, payload) {
    if (low >= high) {
      throw new Error('Invalid interval: low must be strictly less than high');
    }
    this.root = this._insertNode(this.root, low, high, payload);
    this.size++;
  }

  _insertNode(node, low, high, payload) {
    if (!node) {
      return new IntervalNode(low, high, payload);
    }

    if (low < node.low) {
      node.left = this._insertNode(node.left, low, high, payload);
    } else {
      node.right = this._insertNode(node.right, low, high, payload);
    }

    this._update(node);

    const balance = this._getBalance(node);

    // Left-Left
    if (balance > 1 && low < node.left.low) {
      return this._rotateRight(node);
    }
    // Right-Right
    if (balance < -1 && low >= node.right.low) {
      return this._rotateLeft(node);
    }
    // Left-Right
    if (balance > 1 && low >= node.left.low) {
      node.left = this._rotateLeft(node.left);
      return this._rotateRight(node);
    }
    // Right-Left
    if (balance < -1 && low < node.right.low) {
      node.right = this._rotateRight(node.right);
      return this._rotateLeft(node);
    }

    return node;
  }

  queryOverlap(queryLow, queryHigh) {
    const results = [];
    this._queryOverlapNode(this.root, queryLow, queryHigh, results);
    return results;
  }

  _queryOverlapNode(node, qLow, qHigh, results) {
    if (!node) return;

    // Check if current node's interval overlaps [qLow, qHigh]
    // Overlap condition: node.low < qHigh && node.high > qLow
    if (node.low < qHigh && node.high > qLow) {
      results.push({
        low: node.low,
        high: node.high,
        payload: node.payload
      });
    }

    // If left subtree can have overlapping intervals
    if (node.left && node.left.maxHigh > qLow) {
      this._queryOverlapNode(node.left, qLow, qHigh, results);
    }

    // If query could overlap with right subtree
    // Right child only needs to be checked if node.low < qHigh
    if (node.right && node.low < qHigh) {
      this._queryOverlapNode(node.right, qLow, qHigh, results);
    }
  }

  queryPoint(point) {
    return this.queryOverlap(point, point + 1);
  }

  getAll() {
    const results = [];
    const traverse = (node) => {
      if (!node) return;
      traverse(node.left);
      results.push({ low: node.low, high: node.high, payload: node.payload });
      traverse(node.right);
    };
    traverse(this.root);
    return results;
  }
}

module.exports = { IntervalTreeFilter, IntervalNode };
