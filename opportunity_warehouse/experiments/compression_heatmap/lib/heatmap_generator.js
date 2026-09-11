class HeatmapGenerator {
  constructor(options = {}) {
    this.width = options.width || 600;
    this.height = options.height || 220;
  }

  getHeatColor(pct) {
    // 0% -> Green (#10B981), 50% -> Orange (#F59E0B), 100% -> Red (#EF4444)
    if (pct < 30) return '#10B981';
    if (pct < 60) return '#F59E0B';
    return '#EF4444';
  }

  generateHeatmapSvg(buckets = [10, 45, 80, 20, 95]) {
    const bucketWidth = (this.width - 60) / buckets.length;
    const barHeight = 80;
    const startY = 80;

    let rects = [];
    let labels = [];

    for (let i = 0; i < buckets.length; i++) {
      const pct = buckets[i];
      const color = this.getHeatColor(pct);
      const x = 30 + i * bucketWidth;

      rects.push(`<rect x="${x.toFixed(1)}" y="${startY}" width="${(bucketWidth - 6).toFixed(1)}" height="${barHeight}" rx="4" fill="${color}" fill-opacity="0.85" stroke="#334155" stroke-width="1.5" />`);
      labels.push(`<text x="${(x + bucketWidth / 2 - 3).toFixed(1)}" y="${startY + barHeight / 2 + 5}" fill="#ffffff" font-family="system-ui, sans-serif" font-size="14" font-weight="bold" text-anchor="middle">${pct}%</text>`);
      labels.push(`<text x="${(x + bucketWidth / 2 - 3).toFixed(1)}" y="${startY + barHeight + 25}" fill="#94A3B8" font-family="system-ui, sans-serif" font-size="11" text-anchor="middle">Chunk ${i + 1}</text>`);
    }

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${this.width} ${this.height}" width="${this.width}" height="${this.height}" style="background-color: #0F172A; border-radius: 8px;">
  <text x="30" y="45" fill="#F8FAFC" font-family="system-ui, sans-serif" font-size="16" font-weight="bold">Prompt Pruning Density Heatmap</text>
  <text x="30" y="65" fill="#64748B" font-family="system-ui, sans-serif" font-size="12">Red: High Redundancy Pruned | Green: Core Directives Kept</text>
  ${rects.join('\n  ')}
  ${labels.join('\n  ')}
</svg>`;
  }
}

module.exports = { HeatmapGenerator };
