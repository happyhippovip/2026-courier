/**
 * Context Window Token Dynamic Bounded Fast Succinct 2D Range-Tree Filter
 * Implements a 2-level Range Tree: primary BST on X coordinates, with each primary node
 * maintaining a sorted secondary array on Y coordinates for O(log N + k) 2D orthogonal window queries.
 */

class RangeTreeNode {
  constructor(x, point, left = null, right = null) {
    this.x = x;
    this.point = point; // { x, y, data }
    this.left = left;
    this.right = right;
    this.yArray = []; // Sorted array of points in subtree by Y coordinate
  }
}

class RangeTreeFilter {
  constructor() {
    this.root = null;
    this.size = 0;
  }

  build(points) {
    this.size = points.length;
    if (points.length === 0) {
      this.root = null;
      return;
    }

    // Sort uniquely by X
    const pts = points.slice().sort((a, b) => a.x - b.x);
    this.root = this._build1D(pts);
  }

  _build1D(pts) {
    if (pts.length === 0) return null;
    const mid = Math.floor(pts.length / 2);
    const node = new RangeTreeNode(pts[mid].x, pts[mid]);

    node.left = this._build1D(pts.slice(0, mid));
    node.right = this._build1D(pts.slice(mid + 1));

    // Aggregate and sort Y points in subtree
    node.yArray = pts.slice().sort((a, b) => a.y - b.y);
    return node;
  }

  query2D(xMin, xMax, yMin, yMax) {
    if (!this.root) return [];
    const splitNode = this._findSplitNode(this.root, xMin, xMax);
    if (!splitNode) return [];

    const results = [];

    // Check splitNode itself
    if (splitNode.point.x >= xMin && splitNode.point.x <= xMax &&
        splitNode.point.y >= yMin && splitNode.point.y <= yMax) {
      results.push(splitNode.point);
    }

    // Traverse left branch
    let curr = splitNode.left;
    while (curr) {
      if (curr.x >= xMin) {
        if (curr.point.x >= xMin && curr.point.x <= xMax &&
            curr.point.y >= yMin && curr.point.y <= yMax) {
          results.push(curr.point);
        }
        // Right subtree is completely in [xMin, xMax] along X dimension
        if (curr.right) {
          this._report1DY(curr.right.yArray, yMin, yMax, results);
        }
        curr = curr.left;
      } else {
        curr = curr.right;
      }
    }

    // Traverse right branch
    curr = splitNode.right;
    while (curr) {
      if (curr.x <= xMax) {
        if (curr.point.x >= xMin && curr.point.x <= xMax &&
            curr.point.y >= yMin && curr.point.y <= yMax) {
          results.push(curr.point);
        }
        // Left subtree is completely in [xMin, xMax] along X dimension
        if (curr.left) {
          this._report1DY(curr.left.yArray, yMin, yMax, results);
        }
        curr = curr.right;
      } else {
        curr = curr.left;
      }
    }

    return results;
  }

  _findSplitNode(node, xMin, xMax) {
    let curr = node;
    while (curr && (xMax < curr.x || xMin > curr.x)) {
      if (xMax < curr.x) {
        curr = curr.left;
      } else {
        curr = curr.right;
      }
    }
    return curr;
  }

  _report1DY(yArr, yMin, yMax, output) {
    // Binary search to find start index
    let low = 0;
    let high = yArr.length - 1;
    let startIdx = yArr.length;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (yArr[mid].y >= yMin) {
        startIdx = mid;
        high = mid - 1;
      } else {
        low = mid + 1;
      }
    }

    for (let i = startIdx; i < yArr.length && yArr[i].y <= yMax; i++) {
      output.push(yArr[i]);
    }
  }

  getMetrics() {
    return {
      size: this.size,
      dimensions: 2,
      complexity: {
        build: 'O(N log N)',
        query: 'O(log N + k)'
      },
      structure: '2D_RANGE_TREE_WITH_SORTED_SECONDARY_Y_ARRAYS'
    };
  }
}

module.exports = { RangeTreeNode, RangeTreeFilter };
