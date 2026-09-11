/**
 * Dynamic Token Context Splay Tree & Amortized Self-Balancing Ranker
 * Self-adjusting BST bringing recently accessed tokens to the root
 * via zig, zig-zig, and zig-zag tree rotations.
 */

class SplayNode {
  constructor(key, value) {
    this.key = key; // Token score or frequency
    this.value = value;
    this.left = null;
    this.right = null;
  }
}

class SplayTree {
  constructor() {
    this.root = null;
    this.size = 0;
  }

  rightRotate(x) {
    const y = x.left;
    x.left = y.right;
    y.right = x;
    return y;
  }

  leftRotate(x) {
    const y = x.right;
    x.right = y.left;
    y.left = x;
    return y;
  }

  splay(root, key) {
    if (!root || root.key === key) return root;

    // Key lies in left subtree
    if (key < root.key) {
      if (!root.left) return root;

      // Zig-Zig (Left Left)
      if (key < root.left.key) {
        root.left.left = this.splay(root.left.left, key);
        root = this.rightRotate(root);
      } else if (key > root.left.key) {
        // Zig-Zag (Left Right)
        root.left.right = this.splay(root.left.right, key);
        if (root.left.right) {
          root.left = this.leftRotate(root.left);
        }
      }

      return (root.left === null) ? root : this.rightRotate(root);
    } else {
      // Key lies in right subtree
      if (!root.right) return root;

      // Zag-Zig (Right Left)
      if (key < root.right.key) {
        root.right.left = this.splay(root.right.left, key);
        if (root.right.left) {
          root.right = this.rightRotate(root.right);
        }
      } else if (key > root.right.key) {
        // Zag-Zag (Right Right)
        root.right.right = this.splay(root.right.right, key);
        root = this.leftRotate(root);
      }

      return (root.right === null) ? root : this.leftRotate(root);
    }
  }

  insert(key, value) {
    if (!this.root) {
      this.root = new SplayNode(key, value);
      this.size++;
      return;
    }

    this.root = this.splay(this.root, key);

    if (this.root.key === key) {
      this.root.value = value;
      return;
    }

    const newNode = new SplayNode(key, value);
    if (key < this.root.key) {
      newNode.right = this.root;
      newNode.left = this.root.left;
      this.root.left = null;
    } else {
      newNode.left = this.root;
      newNode.right = this.root.right;
      this.root.right = null;
    }

    this.root = newNode;
    this.size++;
  }

  search(key) {
    this.root = this.splay(this.root, key);
    return (this.root && this.root.key === key) ? this.root.value : null;
  }
}

module.exports = { SplayTree, SplayNode };
