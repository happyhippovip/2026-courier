/**
 * Dynamic Token Fibonacci Heap & Ultra-Fast Decrease-Key Pruner
 * Provides O(1) amortized insertion, find-min, and decrease-key operations
 * for dynamic context window saliency annealing and priority token eviction.
 */

class FibNode {
  constructor(key, value) {
    this.key = key; // Saliency score (priority)
    this.value = value;
    this.degree = 0;
    this.marked = false;
    this.parent = null;
    this.child = null;
    this.left = this;
    this.right = this;
  }
}

class FibonacciHeap {
  constructor() {
    this.minNode = null;
    this.totalNodes = 0;
  }

  insert(key, value) {
    const node = new FibNode(key, value);
    if (!this.minNode) {
      this.minNode = node;
    } else {
      this.addToRootList(node);
      if (node.key < this.minNode.key) {
        this.minNode = node;
      }
    }
    this.totalNodes++;
    return node;
  }

  addToRootList(node) {
    node.left = this.minNode;
    node.right = this.minNode.right;
    this.minNode.right.left = node;
    this.minNode.right = node;
  }

  removeFromRootList(node) {
    node.left.right = node.right;
    node.right.left = node.left;
  }

  findMin() {
    return this.minNode ? { key: this.minNode.key, value: this.minNode.value } : null;
  }

  decreaseKey(node, newKey) {
    if (newKey > node.key) {
      throw new Error('New key is greater than current key');
    }
    node.key = newKey;
    const parent = node.parent;

    if (parent && node.key < parent.key) {
      this.cut(node, parent);
      this.cascadingCut(parent);
    }

    if (node.key < this.minNode.key) {
      this.minNode = node;
    }
  }

  cut(node, parent) {
    // Remove node from child list of parent
    if (node.right === node) {
      parent.child = null;
    } else {
      node.left.right = node.right;
      node.right.left = node.left;
      if (parent.child === node) parent.child = node.right;
    }
    parent.degree--;
    this.addToRootList(node);
    node.parent = null;
    node.marked = false;
  }

  cascadingCut(parent) {
    const grandParent = parent.parent;
    if (grandParent) {
      if (!parent.marked) {
        parent.marked = true;
      } else {
        this.cut(parent, grandParent);
        this.cascadingCut(grandParent);
      }
    }
  }

  extractMin() {
    const z = this.minNode;
    if (z) {
      if (z.child) {
        // Add all children to root list
        let c = z.child;
        do {
          const next = c.right;
          this.addToRootList(c);
          c.parent = null;
          c = next;
        } while (c !== z.child);
      }

      this.removeFromRootList(z);
      if (z === z.right) {
        this.minNode = null;
      } else {
        this.minNode = z.right;
        this.consolidate();
      }
      this.totalNodes--;
      return { key: z.key, value: z.value };
    }
    return null;
  }

  consolidate() {
    const maxDegree = Math.floor(Math.log2(this.totalNodes + 1)) * 2 + 1;
    const A = new Array(maxDegree).fill(null);

    const rootNodes = [];
    let curr = this.minNode;
    if (curr) {
      do {
        rootNodes.push(curr);
        curr = curr.right;
      } while (curr !== this.minNode);
    }

    for (const w of rootNodes) {
      let x = w;
      let d = x.degree;
      while (A[d] !== null && A[d] !== x) {
        let y = A[d];
        if (x.key > y.key) {
          const temp = x;
          x = y;
          y = temp;
        }
        this.link(y, x);
        A[d] = null;
        d++;
      }
      A[d] = x;
    }

    this.minNode = null;
    for (const node of A) {
      if (node !== null) {
        if (!this.minNode) {
          this.minNode = node;
          node.left = node;
          node.right = node;
        } else {
          this.addToRootList(node);
          if (node.key < this.minNode.key) {
            this.minNode = node;
          }
        }
      }
    }
  }

  link(y, x) {
    this.removeFromRootList(y);
    y.parent = x;
    if (!x.child) {
      x.child = y;
      y.left = y;
      y.right = y;
    } else {
      y.left = x.child;
      y.right = x.child.right;
      x.child.right.left = y;
      x.child.right = y;
    }
    x.degree++;
    y.marked = false;
  }
}

module.exports = { FibonacciHeap, FibNode };
