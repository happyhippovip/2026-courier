/**
 * subtree_hasher.js - AST Subtree Hashing & Semantic Deduplication Engine
 * Hashes structural AST nodes to detect cross-file identical code blocks and interfaces.
 */
const crypto = require('crypto');

class AstSubtreeHasher {
  constructor(options = {}) {
    this.hashAlgorithm = options.hashAlgorithm || 'sha256';
  }

  normalizeNode(node) {
    if (!node || typeof node !== 'object') return '';
    const clean = {
      type: node.type || 'Node',
      name: node.name || '',
      params: Array.isArray(node.params) ? node.params : [],
      children: []
    };

    if (Array.isArray(node.children)) {
      clean.children = node.children.map(c => this.normalizeNode(c));
    }

    return JSON.stringify(clean);
  }

  computeNodeHash(node) {
    const normalized = this.normalizeNode(node);
    return crypto.createHash(this.hashAlgorithm).update(normalized).digest('hex').slice(0, 16);
  }

  analyzeTree(rootNode) {
    const subtreeMap = new Map();

    const traverse = (node, path = 'root') => {
      if (!node || typeof node !== 'object') return;
      const hash = this.computeNodeHash(node);
      const name = node.name || node.type || 'anonymous';
      const nodePath = path + '.' + name;

      if (!subtreeMap.has(hash)) {
        subtreeMap.set(hash, {
          hash,
          type: node.type || 'Node',
          name,
          occurrences: [nodePath],
          isDuplicate: false
        });
      } else {
        const entry = subtreeMap.get(hash);
        entry.occurrences.push(nodePath);
        entry.isDuplicate = true;
      }

      if (Array.isArray(node.children)) {
        node.children.forEach(child => traverse(child, nodePath));
      }
    };

    traverse(rootNode);

    const duplicates = [];
    const unique = [];
    for (const entry of subtreeMap.values()) {
      if (entry.isDuplicate) {
        duplicates.push(entry);
      } else {
        unique.push(entry);
      }
    }

    const hoistingSuggestions = duplicates.map(d => ({
      hash: d.hash,
      name: d.name,
      count: d.occurrences.length,
      recommendation: 'Hoist structural block "' + d.name + '" to shared prelude module. Eliminates ' + (d.occurrences.length - 1) + ' redundant AST copies.'
    }));

    return {
      totalSubtrees: subtreeMap.size,
      duplicateCount: duplicates.length,
      duplicates,
      hoistingSuggestions,
      timestamp: new Date().toISOString()
    };
  }
}

module.exports = { AstSubtreeHasher };
