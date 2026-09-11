/**
 * Context Window Token Dynamic Bounded Fast Succinct Persistent Treap Filter
 * Implements a pure functional immutable Cartestian Treap (BST on keys, Max-Heap on priorities)
 * with structural sharing across versioned snapshots.
 */

class PersistentTreapNode {
  constructor(key, priority, value, left = null, right = null) {
    this.key = key;
    this.priority = priority;
    this.value = value;
    this.left = left;
    this.right = right;
    this.size = 1 + (left ? left.size : 0) + (right ? right.size : 0);
  }
}

class PersistentTreapFilter {
  constructor() {
    this.snapshots = new Map(); // versionTag -> rootNode
    this.nodeAllocations = 0;
  }

  createNode(key, priority, value, left = null, right = null) {
    this.nodeAllocations++;
    return new PersistentTreapNode(key, priority, value, left, right);
  }

  split(root, key) {
    if (!root) return [null, null];

    if (root.key <= key) {
      const [rLeft, rRight] = this.split(root.right, key);
      const newRoot = this.createNode(root.key, root.priority, root.value, root.left, rLeft);
      return [newRoot, rRight];
    } else {
      const [lLeft, lRight] = this.split(root.left, key);
      const newRoot = this.createNode(root.key, root.priority, root.value, lRight, root.right);
      return [lLeft, newRoot];
    }
  }

  merge(left, right) {
    if (!left) return right;
    if (!right) return left;

    if (left.priority >= right.priority) {
      const newRight = this.merge(left.right, right);
      return this.createNode(left.key, left.priority, left.value, left.left, newRight);
    } else {
      const newLeft = this.merge(left, right.left);
      return this.createNode(right.key, right.priority, right.value, newLeft, right.right);
    }
  }

  insert(root, key, priority, value) {
    const [l, r] = this.split(root, key);
    const [lClean] = this.split(l, key - 0.0000001); // handles duplicate key replacement
    const newNode = this.createNode(key, priority, value, null, null);
    return this.merge(this.merge(lClean, newNode), r);
  }

  delete(root, key) {
    if (!root) return null;
    const [l, r] = this.split(root, key);
    const [lLeft] = this.split(l, key - 0.0000001);
    return this.merge(lLeft, r);
  }

  search(root, key) {
    let curr = root;
    while (curr) {
      if (curr.key === key) return curr;
      if (key < curr.key) {
        curr = curr.left;
      } else {
        curr = curr.right;
      }
    }
    return null;
  }

  rangeQuery(root, minKey, maxKey) {
    const results = [];
    function inorder(node) {
      if (!node) return;
      if (node.key > minKey) inorder(node.left);
      if (node.key >= minKey && node.key <= maxKey) {
        results.push({ key: node.key, value: node.value, priority: node.priority });
      }
      if (node.key < maxKey) inorder(node.right);
    }
    inorder(root);
    return results;
  }

  saveSnapshot(tag, root) {
    this.snapshots.set(tag, root);
    return { tag, rootSize: root ? root.size : 0 };
  }

  getSnapshot(tag) {
    return this.snapshots.get(tag) || null;
  }

  getMetrics() {
    return {
      totalSnapshots: this.snapshots.size,
      nodeAllocations: this.nodeAllocations,
      persistenceModel: 'FUNCTIONAL_IMMUTABLE_STRUCTURAL_SHARING',
      complexity: {
        search: 'O(log N)',
        insert: 'O(log N)',
        splitMerge: 'O(log N)',
        spacePerVersion: 'O(log N)'
      }
    };
  }
}

module.exports = { PersistentTreapNode, PersistentTreapFilter };
