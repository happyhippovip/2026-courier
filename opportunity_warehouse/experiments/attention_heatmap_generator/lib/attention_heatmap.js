/**
 * attention_heatmap.js - Context Window Degradation Heatmap & Attention Visualizer
 * Models and renders attention retention curves across prompt depths for frontier LLMs.
 */
class AttentionHeatmapGenerator {
  constructor() {
    this.models = {
      'claude-3-5-sonnet': { name: 'Claude 3.5 Sonnet', maxTokens: 200000, decayExponent: 1.8, minRetention: 0.72 },
      'gpt-4o': { name: 'GPT-4o', maxTokens: 128000, decayExponent: 2.1, minRetention: 0.65 },
      'gemini-1-5-pro': { name: 'Gemini 1.5 Pro', maxTokens: 2000000, decayExponent: 1.4, minRetention: 0.82 }
    };
  }

  calculateRetentionProfile(modelKey = 'claude-3-5-sonnet', steps = 10) {
    const model = this.models[modelKey] || this.models['claude-3-5-sonnet'];
    const buckets = [];

    for (let i = 0; i <= steps; i++) {
      const depth = i / steps; // 0.0 to 1.0
      // Attention curve: highest at start (depth=0) and end (depth=1), lowest in the middle (depth=0.5)
      const distanceToEdge = Math.min(depth, 1.0 - depth) * 2; // 0.0 at edge, 1.0 at center
      const decayFactor = Math.pow(distanceToEdge, model.decayExponent);
      const retention = Number((1.0 - decayFactor * (1.0 - model.minRetention)).toFixed(3));

      let zone = 'OPTIMAL_RECALL';
      if (retention < 0.75) {
        zone = 'CRITICAL_ATTENTION_DEGRADATION';
      } else if (retention < 0.88) {
        zone = 'MODERATE_ATTENTION_FADING';
      }

      buckets.push({
        depthPercentage: Math.round(depth * 100),
        relativePosition: depth === 0 ? 'START' : (depth === 1 ? 'END' : 'DEPTH_' + Math.round(depth * 100) + '%'),
        estimatedAttentionRetention: retention,
        zone
      });
    }

    return {
      model: model.name,
      maxTokens: model.maxTokens,
      buckets,
      timestamp: new Date().toISOString()
    };
  }

  generateSvg(modelKey = 'claude-3-5-sonnet') {
    const profile = this.calculateRetentionProfile(modelKey, 10);
    const width = 600;
    const height = 240;

    let svg = '<svg width="' + width + '" height="' + height + '" viewBox="0 0 ' + width + ' ' + height + '" xmlns="http://www.w3.org/2000/svg">\n';
    svg += '  <rect width="100%" height="100%" fill="#0d1117" rx="8"/>\n';
    svg += '  <text x="20" y="30" fill="#58a6ff" font-family="monospace" font-size="14" font-weight="bold">Attention Retention Curve: ' + profile.model + '</text>\n';

    // Draw bars
    const barWidth = 45;
    const startX = 35;
    const baseY = 190;
    const maxHeight = 120;

    profile.buckets.forEach((b, idx) => {
      const x = startX + idx * 52;
      const h = Math.round(b.estimatedAttentionRetention * maxHeight);
      const y = baseY - h;
      let color = '#238636'; // green
      if (b.zone === 'CRITICAL_ATTENTION_DEGRADATION') color = '#da3633'; // red
      else if (b.zone === 'MODERATE_ATTENTION_FADING') color = '#d29922'; // yellow

      svg += '  <rect x="' + x + '" y="' + y + '" width="' + barWidth + '" height="' + h + '" fill="' + color + '" rx="3"/>\n';
      svg += '  <text x="' + (x + barWidth / 2) + '" y="' + (baseY + 16) + '" fill="#8b949e" font-family="monospace" font-size="10" text-anchor="middle">' + b.depthPercentage + '%</text>\n';
      svg += '  <text x="' + (x + barWidth / 2) + '" y="' + (y - 5) + '" fill="#c9d1d9" font-family="monospace" font-size="9" text-anchor="middle">' + Math.round(b.estimatedAttentionRetention * 100) + '%</text>\n';
    });

    svg += '  <text x="20" y="225" fill="#8b949e" font-family="monospace" font-size="10">U-Curve Attention Profile | Safe: >88% | Fading: 75-88% | Critical: &lt;75%</text>\n';
    svg += '</svg>';

    return { svg, profile };
  }
}

module.exports = { AttentionHeatmapGenerator };
