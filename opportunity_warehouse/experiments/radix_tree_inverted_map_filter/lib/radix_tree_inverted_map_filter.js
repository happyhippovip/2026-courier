/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Tree Inverted Token Map Filter
 * Compact Patricia/Radix trie where common prefixes are compressed into edge labels,
 * and leaves maintain inverted posting lists for fast boolean intersection queries.
 */

class RadixNode {
  constructor(edgeLabel = '') {
    this.edgeLabel = edgeLabel;
    this.children = new Map(); // firstChar -> RadixNode
    this.postings = new Map(); // docId -> frequency
    this.isTerminal = false;
  }
}

class RadixTreeInvertedMapFilter {
  constructor() {
    this.root = new RadixNode('');
    this.docCount = 0;
  }

  insert(word, docId) {
    if (!word || word.length === 0) return;
    this._insert(this.root, word, docId);
  }

  _insert(node, word, docId) {
    for (const [firstChar, child] of node.children.entries()) {
      const edge = child.edgeLabel;
      let commonLen = 0;
      while (commonLen < edge.length && commonLen < word.length && edge[commonLen] === word[commonLen]) {
        commonLen++;
      }

      if (commonLen > 0) {
        if (commonLen === edge.length) {
          // Exact match of edge: continue recursively
          const remainingWord = word.slice(commonLen);
          if (remainingWord.length === 0) {
            child.isTerminal = true;
            child.postings.set(docId, (child.postings.get(docId) || 0) + 1);
            return;
          } else {
            this._insert(child, remainingWord, docId);
            return;
          }
        } else {
          // Partial match: split existing edge
          const splitNode = new RadixNode(edge.slice(0, commonLen));
          node.children.set(firstChar, splitNode);

          // Update child with remaining edge
          child.edgeLabel = edge.slice(commonLen);
          splitNode.children.set(child.edgeLabel[0], child);

          const remainingWord = word.slice(commonLen);
          if (remainingWord.length === 0) {
            splitNode.isTerminal = true;
            splitNode.postings.set(docId, 1);
          } else {
            const newLeaf = new RadixNode(remainingWord);
            newLeaf.isTerminal = true;
            newLeaf.postings.set(docId, 1);
            splitNode.children.set(remainingWord[0], newLeaf);
          }
          return;
        }
      }
    }

    // No common prefix found with any child: create new child
    const newChild = new RadixNode(word);
    newChild.isTerminal = true;
    newChild.postings.set(docId, 1);
    node.children.set(word[0], newChild);
  }

  search(word) {
    const node = this._findNode(this.root, word);
    if (!node || !node.isTerminal) return [];
    return Array.from(node.postings.entries()).map(([docId, freq]) => ({ docId, freq }));
  }

  _findNode(node, word) {
    if (word.length === 0) return node;

    const firstChar = word[0];
    if (!node.children.has(firstChar)) return null;

    const child = node.children.get(firstChar);
    const edge = child.edgeLabel;

    if (word.startsWith(edge)) {
      return this._findNode(child, word.slice(edge.length));
    }
    return null;
  }

  queryAND(words) {
    if (!words || words.length === 0) return [];
    const postingLists = words.map(w => {
      const res = this.search(w);
      return new Set(res.map(item => item.docId));
    });

    if (postingLists.some(s => s.size === 0)) return [];

    let intersection = postingLists[0];
    for (let i = 1; i < postingLists.length; i++) {
      intersection = new Set([...intersection].filter(x => postingLists[i].has(x)));
    }
    return Array.from(intersection).sort();
  }
}

module.exports = { RadixTreeInvertedMapFilter, RadixNode };
