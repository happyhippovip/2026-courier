/**
 * Context Window Token Dynamic Bounded Fast Succinct Persistent Red-Black Tree Filter
 * Implements Okasaki's pure functional immutable Red-Black Tree,
 * guaranteeing strict O(log N) height, deterministic rebalancing, and structural sharing.
 */

const RED = 'R';
const BLACK = 'B';

class RBNode {
  constructor(color, key, value, left = null, right = null) {
    this.color = color;
    this.key = key;
    this.value = value;
    this.left = left;
    this.right = right;
    this.size = 1 + (left ? left.size : 0) + (right ? right.size : 0);
  }
}

class PersistentRBTreeFilter {
  constructor() {
    this.snapshots = new Map();
    this.nodeAllocations = 0;
  }

  createNode(color, key, value, left = null, right = null) {
    this.nodeAllocations++;
    return new RBNode(color, key, value, left, right);
  }

  // Okasaki's 4-case balance function
  balance(color, key, value, left, right) {
    if (color === BLACK) {
      // Case 1: left is RED and left.left is RED
      if (left && left.color === RED && left.left && left.left.color === RED) {
        return this.createNode(RED, left.key, left.value,
          this.createNode(BLACK, left.left.key, left.left.value, left.left.left, left.left.right),
          this.createNode(BLACK, key, value, left.right, right)
        );
      }
      // Case 2: left is RED and left.right is RED
      if (left && left.color === RED && left.right && left.right.color === RED) {
        return this.createNode(RED, left.right.key, left.right.value,
          this.createNode(BLACK, left.key, left.value, left.left, left.right.left),
          this.createNode(BLACK, key, value, left.right.right, right)
        );
      }
      // Case 3: right is RED and right.left is RED
      if (right && right.color === RED && right.left && right.left.color === RED) {
        return this.createNode(RED, right.left.key, right.left.value,
          this.createNode(BLACK, key, value, left, right.left.left),
          this.createNode(BLACK, right.key, right.value, right.left.right, right.right)
        );
      }
      // Case 4: right is RED and right.right is RED
      if (right && right.color === RED && right.right && right.right.color === RED) {
        return this.createNode(RED, right.key, right.value,
          this.createNode(BLACK, key, value, left, right.left),
          this.createNode(BLACK, right.right.key, right.right.value, right.right.left, right.right.right)
        );
      }
    }
    return this.createNode(color, key, value, left, right);
  }

  insert(root, key, value) {
    const ins = (node) => {
      if (!node) return this.createNode(RED, key, value);
      if (key === node.key) {
        return this.createNode(node.color, key, value, node.left, node.right);
      }
      if (key < node.key) {
        return this.balance(node.color, node.key, node.value, ins(node.left), node.right);
      } else {
        return this.balance(node.color, node.key, node.value, node.left, ins(node.right));
      }
    };

    const newRoot = ins(root);
    // Root must always be colored BLACK
    return this.createNode(BLACK, newRoot.key, newRoot.value, newRoot.left, newRoot.right);
  }

  search(root, key) {
    let curr = root;
    while (curr) {
      if (curr.key === key) return { key: curr.key, value: curr.value, color: curr.color };
      if (key < curr.key) curr = curr.left;
      else curr = curr.right;
    }
    return null;
  }

  rangeQuery(root, minKey, maxKey) {
    const results = [];
    function inorder(node) {
      if (!node) return;
      if (node.key > minKey) inorder(node.left);
      if (node.key >= minKey && node.key <= maxKey) {
        results.push({ key: node.key, value: node.value, color: node.color });
      }
      if (node.key < maxKey) inorder(node.right);
    }
    inorder(root);
    return results;
  }

  saveSnapshot(tag, root) {
    this.snapshots.set(tag, root);
  }

  getSnapshot(tag) {
    return this.snapshots.get(tag) || null;
  }

  getMetrics() {
    return {
      totalSnapshots: this.snapshots.size,
      nodeAllocations: this.nodeAllocations,
      algorithm: 'OKASAKI_FUNCTIONAL_RED_BLACK_TREE',
      complexity: 'O(log N)_WORST_CASE_STRICT'
    };
  }
}

module.exports = { RBNode, PersistentRBTreeFilter };
