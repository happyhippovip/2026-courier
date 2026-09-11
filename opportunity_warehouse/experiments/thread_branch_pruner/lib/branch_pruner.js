/**
 * Multi-Turn Conversation Thread Branch & Prune Engine
 * Models agent reasoning trajectories as an explicit DAG/tree of hypothetical execution branches,
 * pruning abandoned/falsified exploration dead-ends while flattening the verified winning path
 * into an optimal sequential prompt context.
 */

class ThreadBranchPruner {
  constructor() {
    this.nodes = new Map();
    this.rootId = null;
  }

  createThread(rootData = {}) {
    const id = 'node_root_' + Date.now();
    const rootNode = {
      id,
      parentId: null,
      children: [],
      data: rootData,
      status: 'RESOLVED', // root is always resolved
      tokens: Math.max(1, Math.round(JSON.stringify(rootData).length / 4))
    };
    this.nodes.set(id, rootNode);
    this.rootId = id;
    return rootNode;
  }

  addTurn(parentId, turnData, status = 'ACTIVE') {
    if (!this.nodes.has(parentId)) {
      throw new Error('Parent node not found: ' + parentId);
    }
    const id = 'node_' + Math.random().toString(36).substring(2, 8);
    const node = {
      id,
      parentId,
      children: [],
      data: turnData,
      status, // 'ACTIVE', 'RESOLVED', 'ABANDONED', 'FALSIFIED'
      tokens: Math.max(1, Math.round(JSON.stringify(turnData).length / 4))
    };
    this.nodes.set(id, node);
    this.nodes.get(parentId).children.push(id);
    return node;
  }

  markBranchStatus(nodeId, newStatus) {
    if (!this.nodes.has(nodeId)) return;
    const node = this.nodes.get(nodeId);
    node.status = newStatus;
    // Cascade to children
    for (const childId of node.children) {
      this.markBranchStatus(childId, newStatus);
    }
  }

  pruneDeadBranches() {
    let prunedTokens = 0;
    let prunedNodesCount = 0;

    for (const [id, node] of this.nodes.entries()) {
      if (node.status === 'ABANDONED' || node.status === 'FALSIFIED') {
        prunedTokens += node.tokens;
        prunedNodesCount += 1;
      }
    }

    return { prunedNodesCount, prunedTokens };
  }

  linearizeWinningPath(leafId) {
    if (!this.nodes.has(leafId)) {
      throw new Error('Leaf node not found: ' + leafId);
    }

    const path = [];
    let curr = this.nodes.get(leafId);
    while (curr) {
      if (curr.status !== 'ABANDONED' && curr.status !== 'FALSIFIED') {
        path.unshift(curr);
      }
      curr = curr.parentId ? this.nodes.get(curr.parentId) : null;
    }

    const totalTokens = path.reduce((acc, n) => acc + n.tokens, 0);
    return {
      pathSequence: path.map(p => ({ id: p.id, action: p.data.action || p.data.title, status: p.status })),
      totalSteps: path.length,
      totalTokens
    };
  }
}

module.exports = { ThreadBranchPruner };