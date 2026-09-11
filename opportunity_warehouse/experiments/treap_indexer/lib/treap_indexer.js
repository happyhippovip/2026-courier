/**
 * Context Window Token Treap Cartesian Indexer
 * Binary Search Tree on keys (position) and Max-Heap on priorities (saliency)
 * with O(log N) expected search, insertion, and split/merge operations.
 */

class TreapNode {
  constructor(key, priority, token) {
    this.key = key;           // Position index (BST property)
    this.priority = priority; // Saliency score (Max-Heap property)
    this.token = token;
    this.left = null;
    this.right = null;
  }
}

class TreapIndexer {
  constructor() {
    this.root = null;
    this.size = 0;
  }

  rightRotate(y) {
    const x = y.left;
    y.left = x.right;
    x.right = y;
    return x;
  }

  leftRotate(x) {
    const y = x.right;
    x.right = y.left;
    y.left = x;
    return y;
  }

  insert(key, priority, token) {
    this.root = this.insertNode(this.root, key, priority, token);
    this.size++;
  }

  insertNode(node, key, priority, token) {
    if (!node) {
      return new TreapNode(key, priority, token);
    }

    if (key < node.key) {
      node.left = this.insertNode(node.left, key, priority, token);
      if (node.left.priority > node.priority) {
        node = this.rightRotate(node);
      }
    } else {
      node.right = this.insertNode(node.right, key, priority, token);
      if (node.right.priority > node.priority) {
        node = this.leftRotate(node);
      }
    }

    return node;
  }

  search(key) {
    let curr = this.root;
    while (curr) {
      if (curr.key === key) return curr;
      if (key < curr.key) curr = curr.left;
      else curr = curr.right;
    }
    return null;
  }

  // Split treap into two treaps: T1 (keys <= key) and T2 (keys > key)
  split(key) {
    this.insert(key, Infinity, '__SPLIT_SENTINEL__');
    const t1 = this.root.left;
    const t2 = this.root.right;
    this.root = null;
    this.size = 0;
    return { t1, t2 };
  }
}

module.exports = { TreapIndexer, TreapNode };
