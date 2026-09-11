/**
 * Context Window Token Dynamic Bounded Fast Succinct Persistent Treap Priority Deque Filter
 * Implements an immutable double-ended priority queue (min and max extraction) over Cartesian Treap nodes,
 * supporting simultaneous O(log N) retrieval of both lowest and highest saliency tokens with version snapshots.
 */

class TreapDequeNode {
  constructor(key, priority, value, left = null, right = null) {
    this.key = key;
    this.priority = priority;
    this.value = value;
    this.left = left;
    this.right = right;
    this.size = 1 + (left ? left.size : 0) + (right ? right.size : 0);
  }
}

class PersistentTreapDequeFilter {
  constructor() {
    this.snapshots = new Map();
    this.nodeAllocations = 0;
  }

  createNode(key, priority, value, left = null, right = null) {
    this.nodeAllocations++;
    return new TreapDequeNode(key, priority, value, left, right);
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
    const [lClean] = this.split(l, key - 0.0000001);
    const newNode = this.createNode(key, priority, value, null, null);
    return this.merge(this.merge(lClean, newNode), r);
  }

  peekMin(root) {
    if (!root) return null;
    let curr = root;
    while (curr.left) curr = curr.left;
    return { key: curr.key, priority: curr.priority, value: curr.value };
  }

  peekMax(root) {
    if (!root) return null;
    let curr = root;
    while (curr.right) curr = curr.right;
    return { key: curr.key, priority: curr.priority, value: curr.value };
  }

  extractMin(root) {
    if (!root) return [null, null];
    const minItem = this.peekMin(root);
    const [l, r] = this.split(root, minItem.key);
    const [lLeft] = this.split(l, minItem.key - 0.0000001);
    const newRoot = this.merge(lLeft, r);
    return [minItem, newRoot];
  }

  extractMax(root) {
    if (!root) return [null, null];
    const maxItem = this.peekMax(root);
    const [l, r] = this.split(root, maxItem.key);
    const [lLeft] = this.split(l, maxItem.key - 0.0000001);
    const newRoot = this.merge(lLeft, r);
    return [maxItem, newRoot];
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
      dequeOperations: 'O(log N)_MIN_AND_MAX',
      structuralPersistence: 'FUNCTIONAL_CARTEISAN_TREAP'
    };
  }
}

module.exports = { TreapDequeNode, PersistentTreapDequeFilter };
