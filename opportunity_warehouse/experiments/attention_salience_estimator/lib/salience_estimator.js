/**
 * Prompt Attention Salience & Gradient Importance Estimator
 * Calculates empirical token importance using U-shaped positional attention weighting,
 * syntactic entity heuristics, and numerical/code identifier tagging to prune low-salience
 * sentences while preserving core reasoning anchors.
 */

class AttentionSalienceEstimator {
  constructor() {}

  computePositionalWeight(sentenceIndex, totalSentences) {
    if (totalSentences <= 1) return 1.0;
    // U-shaped attention curve: primacy (start) and recency (end) receive higher weight
    const normalizedPos = sentenceIndex / (totalSentences - 1); // 0.0 to 1.0
    const deviation = normalizedPos - 0.5; // -0.5 to +0.5
    return Number((1.0 + 1.5 * (deviation * deviation)).toFixed(3)); // min 1.0 at center, max 1.375 at edges
  }

  scoreToken(token) {
    let score = 1.0;
    // Numerical values, currency, IDs
    if (/\d+/.test(token)) score += 1.5;
    if (/EUR|USD|\$|€/.test(token)) score += 2.0;
    // Code identifiers, snake_case, camelCase
    if (/[A-Z]/.test(token) && /[a-z]/.test(token)) score += 1.2; // camelCase
    if (/_/.test(token)) score += 1.2; // snake_case
    // Critical semantic imperatives
    if (/^(error|warning|critical|must|never|fail|pass|settle|lock|mutex)$/i.test(token)) score += 2.5;
    return score;
  }

  evaluateSentence(sentence, index, totalSentences) {
    const trimmed = sentence.trim();
    const words = trimmed.split(/\s+/).filter(Boolean);
    const tokens = Math.max(1, Math.round(trimmed.length / 4));
    const posWeight = this.computePositionalWeight(index, totalSentences);

    let rawScore = 0;
    for (const w of words) {
      rawScore += this.scoreToken(w);
    }
    const avgWordScore = words.length === 0 ? 0 : rawScore / words.length;
    const finalSalience = Number((avgWordScore * posWeight).toFixed(3));

    return {
      index,
      text: trimmed,
      wordsCount: words.length,
      tokens,
      positionalWeight: posWeight,
      salienceScore: finalSalience
    };
  }

  pruneToTokenBudget(text, tokenBudget = 80) {
    const rawSentences = text.split(/(?<=[.?!])\s+/).map(s => s.trim()).filter(Boolean);
    const totalSentences = rawSentences.length;

    const scored = rawSentences.map((s, idx) => this.evaluateSentence(s, idx, totalSentences));

    // Sort by salience descending to pick highest-importance sentences
    const sortedByScore = [...scored].sort((a, b) => b.salienceScore - a.salienceScore);

    const selected = [];
    let usedTokens = 0;

    for (const item of sortedByScore) {
      if (usedTokens + item.tokens <= tokenBudget) {
        selected.push(item);
        usedTokens += item.tokens;
      }
    }

    // Re-order selected sentences chronologically
    selected.sort((a, b) => a.index - b.index);

    const prunedText = selected.map(s => s.text).join(' ');
    const originalTokens = Math.max(1, Math.round(text.length / 4));
    const tokensSaved = Math.max(0, originalTokens - usedTokens);
    const savingsPercent = Number(((tokensSaved / originalTokens) * 100).toFixed(1));

    return {
      originalTokens,
      prunedTokens: usedTokens,
      tokenBudget,
      tokensSaved,
      savingsPercent,
      retainedSentencesCount: selected.length,
      totalSentencesCount: totalSentences,
      prunedText,
      selectedSentences: selected
    };
  }
}

module.exports = { AttentionSalienceEstimator };