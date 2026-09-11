/**
 * cache_warmer.js - Dynamic Context Cache Warmer & Prompt Segmenter
 * Optimizes prompts for frontier model context caching (Anthropic, OpenAI, DeepSeek)
 * by separating invariant static prefixes from ephemeral dynamic suffixes.
 */
class ContextCacheWarmer {
  constructor(options = {}) {
    this.minCacheTokens = options.minCacheTokens || 1024; // Standard cache boundary minimum
    this.charsPerToken = options.charsPerToken || 4;
    this.cacheDiscountRate = options.cacheDiscountRate || 0.90; // 90% discount on cached tokens
    this.inputCostPerMillion = options.inputCostPerMillion || 3.00; // e.g. Claude 3.5 Sonnet $3/M
  }

  estimateTokens(text) {
    if (!text || typeof text !== 'string') return 0;
    return Math.ceil(text.length / this.charsPerToken);
  }

  segmentPrompt(fullPrompt, dynamicBoundaryMarker = '--- DYNAMIC_USER_INPUT ---') {
    if (!fullPrompt || typeof fullPrompt !== 'string') {
      return { staticPrefix: '', dynamicSuffix: '', isCacheEligible: false };
    }

    let staticPrefix = '';
    let dynamicSuffix = '';

    if (fullPrompt.includes(dynamicBoundaryMarker)) {
      const parts = fullPrompt.split(dynamicBoundaryMarker);
      staticPrefix = parts[0].trim();
      dynamicSuffix = parts.slice(1).join(dynamicBoundaryMarker).trim();
    } else {
      // Automatic heuristics: detect first user turn or query
      const userTurnMatch = fullPrompt.search(/\n(?:User|Human|Task|Query):/i);
      if (userTurnMatch !== -1) {
        staticPrefix = fullPrompt.slice(0, userTurnMatch).trim();
        dynamicSuffix = fullPrompt.slice(userTurnMatch).trim();
      } else {
        // Default: 70% static prefix, 30% dynamic
        const splitIdx = Math.floor(fullPrompt.length * 0.7);
        staticPrefix = fullPrompt.slice(0, splitIdx).trim();
        dynamicSuffix = fullPrompt.slice(splitIdx).trim();
      }
    }

    const staticTokens = this.estimateTokens(staticPrefix);
    const dynamicTokens = this.estimateTokens(dynamicSuffix);
    const totalTokens = staticTokens + dynamicTokens;

    const isCacheEligible = staticTokens >= this.minCacheTokens;

    // Cost calculation per 1,000 runs
    const baselineCost = Number(((totalTokens * 1000 / 1000000) * this.inputCostPerMillion).toFixed(4));
    const cachedTokensCost = (staticTokens * (1 - this.cacheDiscountRate) * 1000 / 1000000) * this.inputCostPerMillion;
    const dynamicTokensCost = (dynamicTokens * 1000 / 1000000) * this.inputCostPerMillion;
    const optimizedCost = Number((cachedTokensCost + dynamicTokensCost).toFixed(4));
    const savingsPerThousandCalls = Number((baselineCost - optimizedCost).toFixed(4));

    return {
      segmentation: {
        staticPrefixLength: staticPrefix.length,
        dynamicSuffixLength: dynamicSuffix.length,
        staticTokens,
        dynamicTokens,
        totalTokens
      },
      cacheEligibility: {
        isEligible: isCacheEligible,
        minRequiredTokens: this.minCacheTokens,
        deficitTokens: isCacheEligible ? 0 : (this.minCacheTokens - staticTokens)
      },
      economics: {
        baselineCostPer1kRunsUSD: baselineCost,
        optimizedCostPer1kRunsUSD: isCacheEligible ? optimizedCost : baselineCost,
        savingsPer1kRunsUSD: isCacheEligible ? savingsPerThousandCalls : 0.0,
        savingsPercentage: isCacheEligible ? Number(((savingsPerThousandCalls / baselineCost) * 100).toFixed(1)) : 0.0
      },
      staticPrefix,
      dynamicSuffix,
      timestamp: new Date().toISOString()
    };
  }
}

module.exports = { ContextCacheWarmer };
