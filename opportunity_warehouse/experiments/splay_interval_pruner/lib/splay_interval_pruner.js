/**
 * Context Window Token Splay Interval Pruner
 * Combines interval tree logic with self-adjusting splay operations to bring
 * frequently accessed token spans to the root for amortized O(log n) access.
 */

class SplayIntervalNode {
  constructor(low, high, payload) {
    this.low = low;
    this.high = high;
    this.payload = payload;
    this.maxHigh = high;
    this.accessCount = 1;
    this.left = null;
    this.right = null;
  }
}

class SplayIntervalPruner {
  constructor() {
    this.root = null;
    this.size = 0;
  }

  _updateMax(node) {
    if (!node) return;
    node.maxHigh = Math.max(
      node.high,
      node.left ? node.left.maxHigh : -Infinity,
      node.right ? node.right.maxHigh : -Infinity
    );
  }

  _rightRotate(x) {
    const y = x.left;
    x.left = y.right;
    y.right = x;
    this._updateMax(x);
    this._updateMax(y);
    return y;
  }

  _leftRotate(x) {
    const y = x.right;
    x.right = y.left;
    y.left = x;
    this._updateMax(x);
    this._updateMax(y);
    return y;
  }

  _splay(root, low) {
    if (!root || root.low === low) return root;

    if (low < root.low) {
      if (!root.left) return root;

      // Zig-Zig (Left-Left)
      if (low < root.left.low) {
        root.left.left = this._splay(root.left.left, low);
        root = this._rightRotate(root);
      }
      // Zig-Zag (Left-Right)
      else if (low > root.left.low) {
        root.left.right = this._splay(root.left.right, low);
        if (root.left.right) {
          root.left = this._leftRotate(root.left);
        }
      }

      return root.left ? this._rightRotate(root) : root;
    } else {
      if (!root.right) return root;

      // Zag-Zig (Right-Left)
      if (low < root.right.low) {
        root.right.left = this._splay(root.right.left, low);
        if (root.right.left) {
          root.right = this._rightRotate(root.right);
        }
      }
      // Zag-Zag (Right-Right)
      else if (low > root.right.low) {
        root.right.right = this._splay(root.right.right, low);
        root = this._leftRotate(root);
      }

      return root.right ? this._leftRotate(root) : root;
    }
  }

  insert(low, high, payload) {
    if (!this.root) {
      this.root = new SplayIntervalNode(low, high, payload);
      this.size++;
      return;
    }

    this.root = this._splay(this.root, low);

    if (this.root.low === low) {
      // Overwrite or update existing
      this.root.high = Math.max(this.root.high, high);
      this.root.payload = payload;
      this._updateMax(this.root);
      return;
    }

    const newNode = new SplayIntervalNode(low, high, payload);
    if (low < this.root.low) {
      newNode.right = this.root;
      newNode.left = this.root.left;
      this.root.left = null;
      this._updateMax(this.root);
      this._updateMax(newNode);
      this.root = newNode;
    } else {
      newNode.left = this.root;
      newNode.right = this.root.right;
      this.root.right = null;
      this._updateMax(this.root);
      this._updateMax(newNode);
      this.root = newNode;
    }
    this.size++;
  }

  queryAccess(low) {
    if (!this.root) return null;
    this.root = this._splay(this.root, low);
    if (this.root.low === low) {
      this.root.accessCount++;
      return this.root;
    }
    return null;
  }

  queryOverlap(qLow, qHigh) {
    const results = [];
    const search = (node) => {
      if (!node) return;
      if (node.low < qHigh && node.high > qLow) {
        results.push({ low: node.low, high: node.high, payload: node.payload, accessCount: node.accessCount });
      }
      if (node.left && node.left.maxHigh > qLow) {
        search(node.left);
      }
      if (node.right && node.low < qHigh) {
        search(node.right);
      }
    };
    search(this.root);
    return results;
  }
}

module.exports = { SplayIntervalPruner, SplayIntervalNode };
