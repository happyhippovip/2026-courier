const crypto = require('crypto');

class PromptCacheOptimizer {
  constructor(options = {}) {
    this.minCachePrefixTokens = options.minCachePrefixTokens || 1024; // Anthropic Claude requires >= 1024 tokens for caching
  }

  hash(text) {
    return crypto.createHash('sha256').update(text || '').digest('hex').slice(0, 16);
  }

  partitionPrompt(fullPrompt) {
    if (!fullPrompt || typeof fullPrompt !== 'string') {
      return { staticPrefix: '', dynamicSuffix: '', cacheEligible: false };
    }

    // Heuristic boundary: Look for dynamic delimiters like Current Date, User Turn, Dynamic Session
    const dynamicMarkers = [
      '\n## Current Session',
      '\n## User Turn',
      '\n## Dynamic Context',
      '\n--- Dynamic Data ---'
    ];

    let splitIndex = -1;
    for (const marker of dynamicMarkers) {
      const idx = fullPrompt.indexOf(marker);
      if (idx !== -1 && (splitIndex === -1 || idx < splitIndex)) {
        splitIndex = idx;
      }
    }

    // If no explicit marker found, split 70% static, 30% dynamic
    if (splitIndex === -1) {
      splitIndex = Math.floor(fullPrompt.length * 0.7);
    }

    const staticPrefix = fullPrompt.slice(0, splitIndex).trim();
    const dynamicSuffix = fullPrompt.slice(splitIndex).trim();
    const staticTokens = Math.ceil(staticPrefix.length / 4);
    const cacheEligible = staticTokens >= this.minCachePrefixTokens;

    return {
      staticPrefix,
      dynamicSuffix,
      staticTokens,
      dynamicTokens: Math.ceil(dynamicSuffix.length / 4),
      cacheEligible,
      prefixHash: this.hash(staticPrefix),
      anthropicPayload: {
        type: 'text',
        text: staticPrefix,
        cache_control: cacheEligible ? { type: 'ephemeral' } : null
      }
    };
  }
}

module.exports = { PromptCacheOptimizer };
