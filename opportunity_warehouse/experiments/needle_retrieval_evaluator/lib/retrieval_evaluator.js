/**
 * Context Window Attention Drift & Needle Retrieval Evaluator
 * Quantifies "lost-in-the-middle" attention attenuation for critical prompt constraints
 * and provides algorithmic re-ordering recommendations.
 */

class NeedleRetrievalEvaluator {
  constructor(options = {}) {
    this.decaySteepness = options.decaySteepness || 2.0; // parabolic attention curve
  }

  calculateAttentionScore(depthPercent) {
    // Normalizes depth to [0, 1].
    // Head (0.0) has attention 1.0
    // Tail (1.0) has attention 0.95 (recency bias)
    // Middle (0.5) experiences worst attention dip (~0.35 - 0.45)
    const d = Math.max(0, Math.min(1, depthPercent / 100));
    // Parabolic U-curve: 1 - 4 * (1 - minAttn) * d * (1 - d)
    const minAttn = 0.38;
    const score = 1 - 4 * (1 - minAttn) * d * (1 - d);
    return Number(score.toFixed(3));
  }

  evaluateNeedleRisk(needle = {}) {
    const id = needle.id || 'unnamed_needle';
    const label = needle.label || id;
    const positionTokens = needle.positionTokens || 0;
    const totalTokens = needle.totalTokens || 10000;
    const priority = needle.priority || 'high'; // 'critical', 'high', 'medium'

    const depthPercent = totalTokens > 0 ? (positionTokens / totalTokens) * 100 : 0;
    const attentionScore = this.calculateAttentionScore(depthPercent);

    // Risk is inverse of attention, weighted by priority
    const priorityMultiplier = priority === 'critical' ? 1.5 : (priority === 'high' ? 1.2 : 1.0);
    const riskScore = Number(((1 - attentionScore) * priorityMultiplier).toFixed(3));

    const needsHoisting = attentionScore < 0.65 && (priority === 'critical' || priority === 'high');

    return {
      needleId: id,
      label,
      priority,
      positionTokens,
      totalTokens,
      depthPercent: Number(depthPercent.toFixed(1)),
      attentionScore,
      riskScore,
      needsHoisting,
      recommendedAction: needsHoisting ? 'HOIST_TO_HEAD_OR_TAIL' : 'MAINTAIN_POSITION'
    };
  }

  auditContextSections(sections = []) {
    let currentTokens = 0;
    const totalTokens = sections.reduce((acc, s) => acc + (s.tokens || 0), 0);

    const evaluated = sections.map(sec => {
      const midPoint = currentTokens + (sec.tokens / 2);
      currentTokens += sec.tokens;

      return this.evaluateNeedleRisk({
        id: sec.id,
        label: sec.label || sec.id,
        positionTokens: midPoint,
        totalTokens,
        priority: sec.priority || 'medium'
      });
    });

    const atRiskCount = evaluated.filter(e => e.needsHoisting).length;
    const meanAttention = Number((evaluated.reduce((acc, e) => acc + e.attentionScore, 0) / (evaluated.length || 1)).toFixed(3));

    return {
      totalTokens,
      totalSections: sections.length,
      meanAttentionScore: meanAttention,
      atRiskCount,
      optimizationRequired: atRiskCount > 0,
      evaluations: evaluated
    };
  }
}

module.exports = { NeedleRetrievalEvaluator };
