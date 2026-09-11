/**
 * Multi-Agent Distributed LWW-Element-Graph Engine
 * Implements a conflict-free Last-Write-Wins Element Graph (LWW-Element-Graph CRDT)
 * for directed multi-agent knowledge graphs with monotonic timestamps and deterministic merge.
 */

class LWWElementGraph {
  constructor(nodeId) {
    this.nodeId = nodeId;
    this.verticesAdd = new Map(); // vId -> timestamp
    this.verticesRemove = new Map(); // vId -> timestamp

    this.edgesAdd = new Map(); // "u->v" -> timestamp
    this.edgesRemove = new Map(); // "u->v" -> timestamp
  }

  addVertex(vId, timestamp = Date.now()) {
    const current = this.verticesAdd.get(vId) || 0;
    if (timestamp > current) {
      this.verticesAdd.set(vId, timestamp);
    }
  }

  removeVertex(vId, timestamp = Date.now()) {
    const current = this.verticesRemove.get(vId) || 0;
    if (timestamp > current) {
      this.verticesRemove.set(vId, timestamp);
    }
  }

  addEdge(u, v, timestamp = Date.now()) {
    // Both vertices must exist
    this.addVertex(u, timestamp);
    this.addVertex(v, timestamp);

    const edgeKey = u + '->' + v;
    const current = this.edgesAdd.get(edgeKey) || 0;
    if (timestamp > current) {
      this.edgesAdd.set(edgeKey, timestamp);
    }
  }

  removeEdge(u, v, timestamp = Date.now()) {
    const edgeKey = u + '->' + v;
    const current = this.edgesRemove.get(edgeKey) || 0;
    if (timestamp > current) {
      this.edgesRemove.set(edgeKey, timestamp);
    }
  }

  hasVertex(vId) {
    const addT = this.verticesAdd.get(vId) || 0;
    const remT = this.verticesRemove.get(vId) || 0;
    return addT > remT;
  }

  hasEdge(u, v) {
    if (!this.hasVertex(u) || !this.hasVertex(v)) return false;
    const edgeKey = u + '->' + v;
    const addT = this.edgesAdd.get(edgeKey) || 0;
    const remT = this.edgesRemove.get(edgeKey) || 0;
    return addT > remT;
  }

  merge(other) {
    for (const [v, t] of other.verticesAdd.entries()) {
      this.verticesAdd.set(v, Math.max(this.verticesAdd.get(v) || 0, t));
    }
    for (const [v, t] of other.verticesRemove.entries()) {
      this.verticesRemove.set(v, Math.max(this.verticesRemove.get(v) || 0, t));
    }
    for (const [e, t] of other.edgesAdd.entries()) {
      this.edgesAdd.set(e, Math.max(this.edgesAdd.get(e) || 0, t));
    }
    for (const [e, t] of other.edgesRemove.entries()) {
      this.edgesRemove.set(e, Math.max(this.edgesRemove.get(e) || 0, t));
    }
  }
}

module.exports = { LWWElementGraph };
