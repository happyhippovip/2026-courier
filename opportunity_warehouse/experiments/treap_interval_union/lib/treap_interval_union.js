/**
 * Treap Interval Union Evaluator
 * Randomized Cartesian tree maintaining token spans [low, high]
 * with heap-ordered priorities for O(log n) expected dynamic interval merging and total coverage union.
 */

class TreapIntervalNode {
  constructor(low, high, payload) {
    this.low = low;
    this.high = high;
    this.payload = payload;
    this.priority = Math.random();
    this.maxHigh = high;
    this.left = null;
    this.right = null;
  }
}

class TreapIntervalUnion {
  constructor() {
    this.root = null;
    this.size = 0;
  }

  _update(node) {
    if (!node) return;
    node.maxHigh = Math.max(
      node.high,
      node.left ? node.left.maxHigh : -Infinity,
      node.right ? node.right.maxHigh : -Infinity
    );
  }

  _rotateRight(y) {
    const x = y.left;
    y.left = x.right;
    x.right = y;
    this._update(y);
    this._update(x);
    return x;
  }

  _rotateLeft(x) {
    const y = x.right;
    x.right = y.left;
    y.left = x;
    this._update(x);
    this._update(y);
    return y;
  }

  insert(low, high, payload) {
    this.root = this._insert(this.root, low, high, payload);
    this.size++;
  }

  _insert(node, low, high, payload) {
    if (!node) {
      return new TreapIntervalNode(low, high, payload);
    }

    if (low < node.low) {
      node.left = this._insert(node.left, low, high, payload);
      if (node.left.priority > node.priority) {
        node = this._rotateRight(node);
      }
    } else {
      node.right = this._insert(node.right, low, high, payload);
      if (node.right.priority > node.priority) {
        node = this._rotateLeft(node);
      }
    }

    this._update(node);
    return node;
  }

  getAllSorted() {
    const list = [];
    const inorder = (n) => {
      if (!n) return;
      inorder(n.left);
      list.push({ low: n.low, high: n.high, payload: n.payload });
      inorder(n.right);
    };
    inorder(this.root);
    return list;
  }

  computeIntervalUnion() {
    const sorted = this.getAllSorted();
    if (sorted.length === 0) return [];

    const merged = [];
    let current = { low: sorted[0].low, high: sorted[0].high };

    for (let i = 1; i < sorted.length; i++) {
      const next = sorted[i];
      if (next.low <= current.high) {
        current.high = Math.max(current.high, next.high);
      } else {
        merged.push(current);
        current = { low: next.low, high: next.high };
      }
    }
    merged.push(current);
    return merged;
  }

  totalCoveredTokens() {
    const unions = this.computeIntervalUnion();
    return unions.reduce((acc, u) => acc + (u.high - u.low), 0);
  }
}

module.exports = { TreapIntervalUnion, TreapIntervalNode };
