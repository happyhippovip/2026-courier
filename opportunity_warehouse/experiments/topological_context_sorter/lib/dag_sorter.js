/**
 * Context Window Topological DAG Sorter & Causal Flow Validator
 * Builds dependency graphs across asynchronous agent tool actions and subagent steps,
 * detects circular causality deadlocks, and computes optimal linear prompt contexts.
 */

class TopologicalDagSorter {
  constructor() {
    this.nodes = new Map();
  }

  addNode(id, dependencies = [], data = {}) {
    this.nodes.set(id, {
      id,
      dependencies: Array.from(new Set(dependencies)),
      data
    });
  }

  detectCycle() {
    const visited = new Set();
    const recStack = new Set();

    const hasCycleUtil = (nodeId) => {
      visited.add(nodeId);
      recStack.add(nodeId);

      const node = this.nodes.get(nodeId);
      if (node) {
        for (const dep of node.dependencies) {
          if (!this.nodes.has(dep)) continue;
          if (!visited.has(dep)) {
            if (hasCycleUtil(dep)) return true;
          } else if (recStack.has(dep)) {
            return true;
          }
        }
      }

      recStack.delete(nodeId);
      return false;
    };

    for (const nodeId of this.nodes.keys()) {
      if (!visited.has(nodeId)) {
        if (hasCycleUtil(nodeId)) return true;
      }
    }
    return false;
  }

  topologicalSort() {
    if (this.detectCycle()) {
      throw new Error('Cyclic dependency detected in task DAG');
    }

    // In-degree calculation
    // Edge is: dependency -> dependent (dep must come before node)
    const inDegree = new Map();
    const adj = new Map();

    for (const nodeId of this.nodes.keys()) {
      inDegree.set(nodeId, 0);
      adj.set(nodeId, []);
    }

    for (const [nodeId, node] of this.nodes.entries()) {
      for (const dep of node.dependencies) {
        if (this.nodes.has(dep)) {
          adj.get(dep).push(nodeId);
          inDegree.set(nodeId, inDegree.get(nodeId) + 1);
        }
      }
    }

    // Kahn's algorithm
    const queue = [];
    for (const [nodeId, deg] of inDegree.entries()) {
      if (deg === 0) queue.push(nodeId);
    }

    const sorted = [];
    while (queue.length > 0) {
      const u = queue.shift();
      sorted.push(this.nodes.get(u));

      for (const v of adj.get(u)) {
        inDegree.set(v, inDegree.get(v) - 1);
        if (inDegree.get(v) === 0) {
          queue.push(v);
        }
      }
    }

    return sorted;
  }

  formatCausalPrompt(sortedNodes = []) {
    const lines = ['--- CAUSAL EXECUTION TRACE ---'];
    sortedNodes.forEach((node, idx) => {
      const deps = node.dependencies.length > 0 ? ' [requires: ' + node.dependencies.join(', ') + ']' : '';
      lines.push((idx + 1) + '. Step ' + node.id + deps + ' => ' + (node.data.action || 'COMPLETED'));
    });
    lines.push('--- END TRACE ---');
    return lines.join('\n');
  }
}

module.exports = { TopologicalDagSorter };