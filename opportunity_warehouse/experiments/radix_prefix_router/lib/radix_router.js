/**
 * Context Window Hierarchical Radix-Tree Prefix Router & KV-Cache Subtree Matcher
 * Compressed prefix trie (Patricia trie) for multi-tenant LLM prompt prefixes,
 * matching common system prompts and tool schemas to shared GPU KV-cache blocks.
 */

class RadixNode {
  constructor(edgeLabel = '', isTerminal = false, value = null, cacheBlockId = null) {
    this.edgeLabel = edgeLabel;
    this.isTerminal = isTerminal;
    this.value = value;
    this.cacheBlockId = cacheBlockId;
    this.children = new Map(); // firstChar -> RadixNode
    this.hitCount = 0;
  }
}

class RadixPrefixRouter {
  constructor() {
    this.root = new RadixNode('');
    this.totalEntries = 0;
  }

  getCommonPrefixLength(str1, str2) {
    let i = 0;
    const maxLen = Math.min(str1.length, str2.length);
    while (i < maxLen && str1.charCodeAt(i) === str2.charCodeAt(i)) {
      i++;
    }
    return i;
  }

  insert(prefixKey, value = null, cacheBlockId = null) {
    if (!prefixKey || typeof prefixKey !== 'string') return;
    let current = this.root;
    let remaining = prefixKey;

    while (remaining.length > 0) {
      const firstChar = remaining[0];
      if (!current.children.has(firstChar)) {
        // Direct new edge
        const newNode = new RadixNode(remaining, true, value, cacheBlockId);
        current.children.set(firstChar, newNode);
        this.totalEntries++;
        return;
      }

      const child = current.children.get(firstChar);
      const commonLen = this.getCommonPrefixLength(child.edgeLabel, remaining);

      if (commonLen === child.edgeLabel.length) {
        // Child's edgeLabel is completely consumed
        remaining = remaining.substring(commonLen);
        if (remaining.length === 0) {
          child.isTerminal = true;
          child.value = value;
          child.cacheBlockId = cacheBlockId;
          return;
        }
        current = child;
      } else {
        // Edge split required
        const existingLabel = child.edgeLabel;
        const commonPrefix = existingLabel.substring(0, commonLen);
        const splitChildEdge = existingLabel.substring(commonLen);
        const newRemainingEdge = remaining.substring(commonLen);

        // Transform child into split branch node
        const intermediate = new RadixNode(commonPrefix, false);
        current.children.set(firstChar, intermediate);

        child.edgeLabel = splitChildEdge;
        intermediate.children.set(splitChildEdge[0], child);

        if (newRemainingEdge.length === 0) {
          intermediate.isTerminal = true;
          intermediate.value = value;
          intermediate.cacheBlockId = cacheBlockId;
        } else {
          const newLeaf = new RadixNode(newRemainingEdge, true, value, cacheBlockId);
          intermediate.children.set(newRemainingEdge[0], newLeaf);
        }
        this.totalEntries++;
        return;
      }
    }
  }

  findLongestPrefix(searchString) {
    let current = this.root;
    let remaining = searchString;
    let matchedPrefix = '';
    const matchedNodes = [];

    while (remaining.length > 0) {
      const firstChar = remaining[0];
      if (!current.children.has(firstChar)) {
        break;
      }

      const child = current.children.get(firstChar);
      const commonLen = this.getCommonPrefixLength(child.edgeLabel, remaining);

      if (commonLen === child.edgeLabel.length) {
        matchedPrefix += child.edgeLabel;
        child.hitCount++;
        matchedNodes.push(child);
        remaining = remaining.substring(commonLen);
        current = child;
      } else {
        // Partial match along edge
        matchedPrefix += child.edgeLabel.substring(0, commonLen);
        break;
      }
    }

    const deepestTerminal = [...matchedNodes].reverse().find(n => n.isTerminal) || null;
    const cacheBlocks = matchedNodes
      .filter(n => n.cacheBlockId !== null)
      .map(n => n.cacheBlockId);

    return {
      matchedPrefix,
      matchedLength: matchedPrefix.length,
      deepestTerminal,
      matchedNodesCount: matchedNodes.length,
      cacheBlocks
    };
  }

  routePrompt(promptText) {
    const result = this.findLongestPrefix(promptText);
    const totalChars = promptText.length;
    const reuseRatio = totalChars > 0 ? (result.matchedLength / totalChars) : 0;

    return {
      totalChars,
      matchedChars: result.matchedLength,
      cacheReusePercentage: Number((reuseRatio * 100).toFixed(2)),
      reusableCacheBlocks: result.cacheBlocks,
      unmatchedSuffixChars: totalChars - result.matchedLength
    };
  }
}

module.exports = { RadixPrefixRouter, RadixNode };
