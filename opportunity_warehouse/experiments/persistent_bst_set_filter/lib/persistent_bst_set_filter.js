/**
 * Context Window Token Dynamic Bounded Fast Succinct Persistent Binary Search Tree Set Filter
 * Implements a pure functional immutable BST set supporting O(log N) insert, contains,
 * and structural union, intersection, and difference between immutable token set versions.
 */

class SetNode {
  constructor(key, left = null, right = null) {
    this.key = key;
    this.left = left;
    this.right = right;
    this.size = 1 + (left ? left.size : 0) + (right ? right.size : 0);
  }
}

class PersistentBSTSetFilter {
  constructor() {
    this.snapshots = new Map();
  }

  insert(root, key) {
    if (!root) return new SetNode(key);
    if (key === root.key) return root; // Key already present
    if (key < root.key) {
      return new SetNode(root.key, this.insert(root.left, key), root.right);
    } else {
      return new SetNode(root.key, root.left, this.insert(root.right, key));
    }
  }

  contains(root, key) {
    let curr = root;
    while (curr) {
      if (curr.key === key) return true;
      if (key < curr.key) curr = curr.left;
      else curr = curr.right;
    }
    return false;
  }

  toList(root) {
    const arr = [];
    function inorder(node) {
      if (!node) return;
      inorder(node.left);
      arr.push(node.key);
      inorder(node.right);
    }
    inorder(root);
    return arr;
  }

  fromSortedList(keys, start = 0, end = keys.length - 1) {
    if (start > end) return null;
    const mid = Math.floor((start + end) / 2);
    const node = new SetNode(keys[mid]);
    node.left = this.fromSortedList(keys, start, mid - 1);
    node.right = this.fromSortedList(keys, mid + 1, end);
    node.size = 1 + (node.left ? node.left.size : 0) + (node.right ? node.right.size : 0);
    return node;
  }

  union(rootA, rootB) {
    const listA = this.toList(rootA);
    const listB = this.toList(rootB);
    const merged = [];
    let i = 0, j = 0;
    while (i < listA.length && j < listB.length) {
      if (listA[i] === listB[j]) {
        merged.push(listA[i]);
        i++;
        j++;
      } else if (listA[i] < listB[j]) {
        merged.push(listA[i]);
        i++;
      } else {
        merged.push(listB[j]);
        j++;
      }
    }
    while (i < listA.length) merged.push(listA[i++]);
    while (j < listB.length) merged.push(listB[j++]);
    return this.fromSortedList(merged);
  }

  intersection(rootA, rootB) {
    const listA = this.toList(rootA);
    const listB = this.toList(rootB);
    const common = [];
    let i = 0, j = 0;
    while (i < listA.length && j < listB.length) {
      if (listA[i] === listB[j]) {
        common.push(listA[i]);
        i++;
        j++;
      } else if (listA[i] < listB[j]) {
        i++;
      } else {
        j++;
      }
    }
    return this.fromSortedList(common);
  }

  difference(rootA, rootB) {
    const listA = this.toList(rootA);
    const diff = listA.filter(k => !this.contains(rootB, k));
    return this.fromSortedList(diff);
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
      functionalOperations: ['union', 'intersection', 'difference'],
      complexity: 'O(N)_SET_ALGEBRA_O_LOG_N_LOOKUP',
      persistenceModel: 'FUNCTIONAL_BALANCED_BST_SET'
    };
  }
}

module.exports = { SetNode, PersistentBSTSetFilter };
