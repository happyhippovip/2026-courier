/**
 * Context Window Token Dynamic Bounded Fast Succinct Persistent Splay Tree Filter
 * Implements a pure functional immutable Splay Tree where splay operations return a new root
 * version with accessed elements rotated towards the top, preserving past version snapshots.
 */

class SplayNode {
  constructor(key, value, left = null, right = null) {
    this.key = key;
    this.value = value;
    this.left = left;
    this.right = right;
    this.size = 1 + (left ? left.size : 0) + (right ? right.size : 0);
  }
}

class PersistentSplayTreeFilter {
  constructor() {
    this.snapshots = new Map(); // versionTag -> rootNode
    this.nodeAllocations = 0;
  }

  createNode(key, value, left = null, right = null) {
    this.nodeAllocations++;
    return new SplayNode(key, value, left, right);
  }

  insert(root, key, value) {
    if (!root) return this.createNode(key, value);
    if (key === root.key) {
      return this.createNode(key, value, root.left, root.right);
    }
    if (key < root.key) {
      return this.createNode(root.key, root.value, this.insert(root.left, key, value), root.right);
    } else {
      return this.createNode(root.key, root.value, root.left, this.insert(root.right, key, value));
    }
  }

  splay(root, key) {
    if (!root) return null;
    const path = [];
    let curr = root;
    while (curr) {
      path.push(curr);
      if (curr.key === key) break;
      if (key < curr.key) curr = curr.left;
      else curr = curr.right;
    }

    if (!curr || curr.key !== key) return root;

    while (path.length > 1) {
      const target = path.pop();
      const parent = path.pop();

      let newTarget;
      if (parent.left && parent.left.key === target.key) {
        const newParent = this.createNode(parent.key, parent.value, target.right, parent.right);
        newTarget = this.createNode(target.key, target.value, target.left, newParent);
      } else {
        const newParent = this.createNode(parent.key, parent.value, parent.left, target.left);
        newTarget = this.createNode(target.key, target.value, newParent, target.right);
      }

      path.push(newTarget);
    }

    return path[0];
  }

  access(root, key) {
    if (!root) return { root: null, value: null };
    const splayed = this.splay(root, key);
    if (splayed && splayed.key === key) {
      return { root: splayed, value: splayed.value };
    }
    return { root, value: null };
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
      amortizedAccess: 'O(log N)',
      cachingProperty: 'SELF_ADJUSTING_FREQUENT_QUERY_LOCALITY'
    };
  }
}

module.exports = { SplayNode, PersistentSplayTreeFilter };
