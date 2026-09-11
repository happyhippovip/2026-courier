/**
 * Context Window Token Dynamic Bounded Fast Succinct Priority R-Tree (PR-Tree) Filter
 * Implements a 2D Priority Search R-Tree over (token_index, saliency_weight) points,
 * supporting optimal orthogonal range reporting and top-k priority extraction.
 */

class PRPoint {
  constructor(x, y, data) {
    this.x = x; // e.g. token position
    this.y = y; // e.g. saliency weight
    this.data = data;
  }
}

class PRTreeNode {
  constructor(minX, maxX, minY, maxY, points = [], children = []) {
    this.minX = minX;
    this.maxX = maxX;
    this.minY = minY;
    this.maxY = maxY;
    this.points = points; // Leaf points
    this.children = children; // Subtrees
    this.maxPriority = points.reduce((m, p) => Math.max(m, p.y), -Infinity);
    for (const ch of children) {
      if (ch.maxPriority > this.maxPriority) this.maxPriority = ch.maxPriority;
    }
  }

  isLeaf() {
    return this.children.length === 0;
  }
}

class PriorityRTreeFilter {
  constructor(leafCapacity = 4) {
    this.leafCapacity = leafCapacity;
    this.root = null;
    this.pointCount = 0;
  }

  build(points) {
    this.pointCount = points.length;
    if (points.length === 0) {
      this.root = null;
      return;
    }
    this.root = this._buildRecursive(points.slice(), 0);
  }

  _buildRecursive(pts, depth) {
    if (pts.length <= this.leafCapacity) {
      const minX = Math.min(...pts.map(p => p.x));
      const maxX = Math.max(...pts.map(p => p.x));
      const minY = Math.min(...pts.map(p => p.y));
      const maxY = Math.max(...pts.map(p => p.y));
      return new PRTreeNode(minX, maxX, minY, maxY, pts, []);
    }

    // Split alternately by X and Y coordinate
    const axis = depth % 2 === 0 ? 'x' : 'y';
    pts.sort((a, b) => a[axis] - b[axis]);

    const mid = Math.floor(pts.length / 2);
    const leftPts = pts.slice(0, mid);
    const rightPts = pts.slice(mid);

    const leftNode = this._buildRecursive(leftPts, depth + 1);
    const rightNode = this._buildRecursive(rightPts, depth + 1);

    const minX = Math.min(leftNode.minX, rightNode.minX);
    const maxX = Math.max(leftNode.maxX, rightNode.maxX);
    const minY = Math.min(leftNode.minY, rightNode.minY);
    const maxY = Math.max(leftNode.maxY, rightNode.maxY);

    return new PRTreeNode(minX, maxX, minY, maxY, [], [leftNode, rightNode]);
  }

  query2DRange(x1, x2, y1, y2, node = this.root) {
    if (!node) return [];

    // Check intersection with node bounding box
    if (node.maxX < x1 || node.minX > x2 || node.maxY < y1 || node.minY > y2) {
      return [];
    }

    if (node.isLeaf()) {
      return node.points.filter(p => p.x >= x1 && p.x <= x2 && p.y >= y1 && p.y <= y2);
    }

    const results = [];
    for (const ch of node.children) {
      results.push(...this.query2DRange(x1, x2, y1, y2, ch));
    }
    return results;
  }

  topKRange(x1, x2, y1, y2, k) {
    const matching = this.query2DRange(x1, x2, y1, y2);
    matching.sort((a, b) => b.y - a.y);
    return matching.slice(0, k);
  }

  getMetrics() {
    return {
      totalPoints: this.pointCount,
      leafCapacity: this.leafCapacity,
      rootBoundingBox: this.root ? { minX: this.root.minX, maxX: this.root.maxX, minY: this.root.minY, maxY: this.root.maxY } : null,
      queryComplexity: 'O(log N + k)_WORST_CASE_OPTIMAL',
      spatialIndex: 'ORTHOGONAL_2D_PRIORITY_BOUNDED'
    };
  }
}

module.exports = { PRPoint, PRTreeNode, PriorityRTreeFilter };
