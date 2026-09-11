/**
 * Context Window Token Disjoint-Set Union-Find with Path Compression & Rank
 * Implements near-constant inverse Ackermann O(alpha(N)) operations
 * for fast semantic co-reference clustering and component tracking.
 */

class DisjointSetUnion {
  constructor() {
    this.parent = new Map();
    this.rank = new Map();
    this.size = new Map();
    this.totalComponents = 0;
  }

  makeSet(x) {
    if (!this.parent.has(x)) {
      this.parent.set(x, x);
      this.rank.set(x, 0);
      this.size.set(x, 1);
      this.totalComponents++;
    }
  }

  // Find with two-pass full path compression
  find(x) {
    if (!this.parent.has(x)) this.makeSet(x);
    let root = x;
    while (root !== this.parent.get(root)) {
      root = this.parent.get(root);
    }
    // Path compression
    let curr = x;
    while (curr !== root) {
      const next = this.parent.get(curr);
      this.parent.set(curr, root);
      curr = next;
    }
    return root;
  }

  // Union by rank
  union(x, y) {
    const rootX = this.find(x);
    const rootY = this.find(y);
    if (rootX === rootY) return false;

    const rankX = this.rank.get(rootX);
    const rankY = this.rank.get(rootY);
    const sizeX = this.size.get(rootX);
    const sizeY = this.size.get(rootY);

    if (rankX < rankY) {
      this.parent.set(rootX, rootY);
      this.size.set(rootY, sizeX + sizeY);
    } else if (rankX > rankY) {
      this.parent.set(rootY, rootX);
      this.size.set(rootX, sizeX + sizeY);
    } else {
      this.parent.set(rootY, rootX);
      this.rank.set(rootX, rankX + 1);
      this.size.set(rootX, sizeX + sizeY);
    }

    this.totalComponents--;
    return true;
  }

  connected(x, y) {
    return this.find(x) === this.find(y);
  }

  getComponentSize(x) {
    return this.size.get(this.find(x));
  }
}

module.exports = { DisjointSetUnion };
