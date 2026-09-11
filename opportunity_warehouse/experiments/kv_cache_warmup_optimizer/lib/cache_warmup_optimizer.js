/**
 * Prompt Attention Anchor & KV-Cache Warmup Optimizer
 * Partitions agent prompts into static immutable prefixes (guaranteed cache hits),
 * canonicalizes whitespace and system instructions, and quantifies prefix cache hit rates
 * to minimize Time-To-First-Token (TTFT) and inference prefill compute.
 */

class KvCacheWarmupOptimizer {
  constructor() {}

  canonicalizePrefix(text = '') {
    return text
      .replace(/\r\n/g, '\n')
      .split('\n')
      .map(line => line.replace(/[ \t]+/g, ' ').trim())
      .filter(line => line.length > 0)
      .join('\n');
  }

  partitionPrompt(fullPrompt, delimiter = '--- DYNAMIC_CONTEXT ---') {
    const parts = fullPrompt.split(delimiter);
    const staticSection = parts[0] ? this.canonicalizePrefix(parts[0]) : '';
    const dynamicSection = parts.slice(1).join(delimiter).trim();

    const staticTokens = Math.max(1, Math.round(staticSection.length / 4));
    const dynamicTokens = Math.max(0, Math.round(dynamicSection.length / 4));
    const totalTokens = staticTokens + dynamicTokens;

    return {
      staticPrefix: staticSection,
      dynamicTail: dynamicSection,
      staticTokens,
      dynamicTokens,
      totalTokens,
      cachableRatio: Number((staticTokens / totalTokens).toFixed(3))
    };
  }

  computeCommonPrefixLength(str1 = '', str2 = '') {
    const len = Math.min(str1.length, str2.length);
    let i = 0;
    while (i < len && str1[i] === str2[i]) {
      i++;
    }
    return i;
  }

  evaluateCacheHitMetrics(basePrefix, incomingPrefix, prefillCostPer1k = 0.005) {
    const canonicalBase = this.canonicalizePrefix(basePrefix);
    const canonicalInc = this.canonicalizePrefix(incomingPrefix);

    const commonBytes = this.computeCommonPrefixLength(canonicalBase, canonicalInc);
    const baseTokens = Math.max(1, Math.round(canonicalBase.length / 4));
    const incTokens = Math.max(1, Math.round(canonicalInc.length / 4));
    const cachedTokens = Math.round(commonBytes / 4);

    const cacheHitRate = Number((cachedTokens / incTokens).toFixed(3));
    const latencyReductionPercent = Number((cacheHitRate * 85).toFixed(1));
    const estimatedSavingsUsd = Number(((cachedTokens / 1000) * prefillCostPer1k).toFixed(5));

    return {
      baseTokens,
      incomingTokens: incTokens,
      cachedTokens,
      cacheHitRate,
      latencyReductionPercent,
      estimatedSavingsUsd,
      isExactPrefixMatch: commonBytes === canonicalBase.length
    };
  }
}

module.exports = { KvCacheWarmupOptimizer };