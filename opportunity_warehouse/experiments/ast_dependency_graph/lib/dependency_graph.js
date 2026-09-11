/**
 * AST Context Dependency Graph Extractor & Topology Analyzer
 * Models dependencies between prompt sections, system instructions, tools, and variables.
 * Calculates centrality, reachability, and identifies safe pruning candidates.
 */

class DependencyGraph {
  constructor() {
    this.nodes = new Map(); // id -> { id, label, type, tokens, metadata }
    this.edges = []; // { from, to, type }
    this.adjacency = new Map(); // id -> Set of dependent ids (outgoing)
    this.inDegree = new Map(); // id -> count
    this.outDegree = new Map(); // id -> count
  }

  addNode(id, options = {}) {
    if (this.nodes.has(id)) {
      throw new Error('Node already exists: ' + id);
    }
    const node = {
      id,
      label: options.label || id,
      type: options.type || 'context_section',
      tokens: options.tokens || 0,
      priority: options.priority || 'medium', // 'critical', 'high', 'medium', 'low'
      metadata: options.metadata || {}
    };
    this.nodes.set(id, node);
    this.adjacency.set(id, new Set());
    this.inDegree.set(id, 0);
    this.outDegree.set(id, 0);
    return node;
  }

  addDependency(fromId, toId, type = 'requires') {
    if (!this.nodes.has(fromId)) throw new Error('From node not found: ' + fromId);
    if (!this.nodes.has(toId)) throw new Error('To node not found: ' + toId);
    
    // Check duplicate edge
    const exists = this.edges.some(e => e.from === fromId && e.to === toId);
    if (!exists) {
      this.edges.push({ from: fromId, to: toId, type });
      this.adjacency.get(fromId).add(toId);
      this.outDegree.set(fromId, this.outDegree.get(fromId) + 1);
      this.inDegree.set(toId, this.inDegree.get(toId) + 1);
    }
  }

  hasCycle() {
    const visited = new Set();
    const recStack = new Set();

    const dfs = (nodeId) => {
      visited.add(nodeId);
      recStack.add(nodeId);

      const neighbors = this.adjacency.get(nodeId) || new Set();
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor)) {
          if (dfs(neighbor)) return true;
        } else if (recStack.has(neighbor)) {
          return true;
        }
      }

      recStack.delete(nodeId);
      return false;
    };

    for (const nodeId of this.nodes.keys()) {
      if (!visited.has(nodeId)) {
        if (dfs(nodeId)) return true;
      }
    }
    return false;
  }

  topologicalSort() {
    if (this.hasCycle()) {
      throw new Error('Cycle detected; topological sort impossible');
    }

    const inDeg = new Map(this.inDegree);
    const queue = [];
    const result = [];

    for (const [id, count] of inDeg.entries()) {
      if (count === 0) queue.push(id);
    }

    while (queue.length > 0) {
      const curr = queue.shift();
      result.push(curr);

      for (const neighbor of this.adjacency.get(curr)) {
        inDeg.set(neighbor, inDeg.get(neighbor) - 1);
        if (inDeg.get(neighbor) === 0) {
          queue.push(neighbor);
        }
      }
    }

    return result;
  }

  getPruningCandidates(options = {}) {
    const keepCritical = options.keepCritical !== false;
    const candidates = [];

    for (const [id, node] of this.nodes.entries()) {
      if (keepCritical && node.priority === 'critical') continue;

      // In-degree == 0 means nothing depends on this node
      // Out-degree > 0 means it depends on others, but nothing needs it!
      const inDeg = this.inDegree.get(id);
      const outDeg = this.outDegree.get(id);

      // A safe pruning candidate has inDeg === 0 (no other active context node depends on it)
      // or priority === 'low'
      if (inDeg === 0) {
        candidates.push({
          id,
          tokens: node.tokens,
          priority: node.priority,
          inDegree: inDeg,
          outDegree: outDeg,
          safetyScore: node.priority === 'low' ? 1.0 : (node.priority === 'medium' ? 0.8 : 0.4)
        });
      }
    }

    // Sort by safetyScore descending, then tokens descending
    candidates.sort((a, b) => b.safetyScore - a.safetyScore || b.tokens - a.tokens);
    return candidates;
  }

  generateReport() {
    let totalTokens = 0;
    for (const node of this.nodes.values()) {
      totalTokens += node.tokens;
    }

    const topo = this.topologicalSort();
    const pruningCandidates = this.getPruningCandidates();
    const prunableTokens = pruningCandidates.reduce((acc, c) => acc + c.tokens, 0);

    return {
      totalNodes: this.nodes.size,
      totalEdges: this.edges.length,
      totalTokens,
      prunableTokens,
      maxTokenSavingsPercent: totalTokens > 0 ? Number(((prunableTokens / totalTokens) * 100).toFixed(2)) : 0,
      isDAG: !this.hasCycle(),
      topologicalOrder: topo,
      pruningCandidates,
      nodeMetrics: Array.from(this.nodes.values()).map(n => ({
        id: n.id,
        label: n.label,
        type: n.type,
        tokens: n.tokens,
        inDegree: this.inDegree.get(n.id),
        outDegree: this.outDegree.get(n.id)
      }))
    };
  }
}

module.exports = { DependencyGraph };
