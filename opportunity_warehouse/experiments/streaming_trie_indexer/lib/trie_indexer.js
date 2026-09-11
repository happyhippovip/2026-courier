/**
 * Context Window Streaming Trie Tokenizer & Prefix Tree Indexer
 * Maintains an incremental character-level prefix tree (Trie) over streaming agent context,
 * providing O(L) prefix autocomplete, entity frequency tracking, and instantaneous symbol lookups.
 */

class TrieNode {
  constructor() {
    this.children = new Map();
    this.isEndOfWord = false;
    this.frequency = 0;
    this.metadata = null;
  }
}

class StreamingTrieIndexer {
  constructor() {
    this.root = new TrieNode();
    this.totalWordsIndexed = 0;
  }

  insert(word, metadata = {}) {
    if (!word || typeof word !== 'string') return;
    const normalized = word.toLowerCase().trim();
    if (normalized.length === 0) return;

    let current = this.root;
    for (let i = 0; i < normalized.length; i++) {
      const ch = normalized[i];
      if (!current.children.has(ch)) {
        current.children.set(ch, new TrieNode());
      }
      current = current.children.get(ch);
    }

    current.isEndOfWord = true;
    current.frequency += 1;
    current.metadata = { ...current.metadata, ...metadata, lastSeen: Date.now() };
    this.totalWordsIndexed += 1;
  }

  search(word) {
    if (!word) return null;
    const normalized = word.toLowerCase().trim();
    let current = this.root;
    for (let i = 0; i < normalized.length; i++) {
      const ch = normalized[i];
      if (!current.children.has(ch)) return null;
      current = current.children.get(ch);
    }
    return current.isEndOfWord ? { frequency: current.frequency, metadata: current.metadata } : null;
  }

  findWithPrefix(prefix) {
    if (!prefix) return [];
    const normalized = prefix.toLowerCase().trim();
    let current = this.root;
    for (let i = 0; i < normalized.length; i++) {
      const ch = normalized[i];
      if (!current.children.has(ch)) return [];
      current = current.children.get(ch);
    }

    const results = [];
    const collect = (node, currentStr) => {
      if (node.isEndOfWord) {
        results.push({ word: currentStr, frequency: node.frequency, metadata: node.metadata });
      }
      for (const [ch, childNode] of node.children.entries()) {
        collect(childNode, currentStr + ch);
      }
    };

    collect(current, normalized);
    results.sort((a, b) => b.frequency - a.frequency);
    return results;
  }

  indexStreamChunk(chunkText, chunkMeta = {}) {
    const tokens = chunkText.split(/[^A-Za-z0-9_]+/).filter(t => t.length > 2);
    for (const t of tokens) {
      this.insert(t, chunkMeta);
    }
    return { indexedTokenCount: tokens.length, totalIndexed: this.totalWordsIndexed };
  }
}

module.exports = { StreamingTrieIndexer };