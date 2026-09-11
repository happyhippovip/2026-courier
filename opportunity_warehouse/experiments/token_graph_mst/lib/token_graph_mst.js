/**
 * Token Graph Minimum Spanning Tree (MST) & Pruned Discourse Summarizer
 * Constructs co-occurrence graph of discourse tokens and applies Kruskal's
 * Union-Find MST algorithm to isolate the core semantic backbone.
 */

class DisjointSet {
  constructor() {
    this.parent = new Map();
    this.rank = new Map();
  }

  makeSet(x) {
    if (!this.parent.has(x)) {
      this.parent.set(x, x);
      this.rank.set(x, 0);
    }
  }

  find(x) {
    if (this.parent.get(x) !== x) {
      this.parent.set(x, this.find(this.parent.get(x)));
    }
    return this.parent.get(x);
  }

  union(x, y) {
    const rootX = this.find(x);
    const rootY = this.find(y);
    if (rootX === rootY) return false;

    const rankX = this.rank.get(rootX);
    const rankY = this.rank.get(rootY);

    if (rankX < rankY) {
      this.parent.set(rootX, rootY);
    } else if (rankX > rankY) {
      this.parent.set(rootY, rootX);
    } else {
      this.parent.set(rootY, rootX);
      this.rank.set(rootX, rankX + 1);
    }
    return true;
  }
}

class TokenGraphMST {
  constructor() {
    this.nodes = new Set();
    this.edges = [];
  }

  addNode(token) {
    this.nodes.add(token);
  }

  addEdge(u, v, weight) {
    this.nodes.add(u);
    this.nodes.add(v);
    this.edges.push({ u, v, weight });
  }

  computeMST() {
    const ds = new DisjointSet();
    for (const node of this.nodes) {
      ds.makeSet(node);
    }

    // Sort edges ascending by weight (cost)
    const sortedEdges = [...this.edges].sort((a, b) => a.weight - b.weight);
    const mstEdges = [];
    let totalWeight = 0;

    for (const edge of sortedEdges) {
      if (ds.union(edge.u, edge.v)) {
        mstEdges.push(edge);
        totalWeight += edge.weight;
      }
    }

    return {
      nodeCount: this.nodes.size,
      originalEdgeCount: this.edges.length,
      mstEdgeCount: mstEdges.length,
      totalWeight,
      mstEdges,
      compressionRatio: this.edges.length > 0 ? (1 - (mstEdges.length / this.edges.length)) : 0
    };
  }
}

module.exports = { TokenGraphMST, DisjointSet };
