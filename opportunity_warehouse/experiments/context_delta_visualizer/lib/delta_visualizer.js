/**
 * Context Window Semantic Compression Heatmap & Per-Turn Token Delta Visualizer
 * Generates ASCII sparklines and SVG charts displaying turn-by-turn context pruning efficiency.
 */

class ContextDeltaVisualizer {
  constructor() {
    this.turnRecords = [];
  }

  recordTurn(turnNumber, originalTokens, prunedTokens, category = 'general') {
    const saved = Math.max(0, originalTokens - prunedTokens);
    const savingsPercent = originalTokens > 0 ? Number(((saved / originalTokens) * 100).toFixed(1)) : 0;
    const record = {
      turnNumber,
      category,
      originalTokens,
      prunedTokens,
      tokensSaved: saved,
      savingsPercent
    };
    this.turnRecords.push(record);
    return record;
  }

  generateAsciiWaterfall() {
    const lines = [
      '=== SYMPHONY CONTEXT COMPRESSION WATERFALL ===',
      'TURN | CATEGORY     | ORIG  | PRUNED | SAVED | RATIO | VISUAL'
    ];

    for (const r of this.turnRecords) {
      const barLength = Math.round(r.savingsPercent / 5); // 0 to 20 chars
      const bar = '█'.repeat(barLength) + '░'.repeat(20 - barLength);
      const cat = r.category.padEnd(12, ' ').slice(0, 12);
      const orig = String(r.originalTokens).padStart(5, ' ');
      const pruned = String(r.prunedTokens).padStart(6, ' ');
      const saved = String(r.tokensSaved).padStart(5, ' ');
      const pct = (r.savingsPercent + '%').padStart(5, ' ');

      lines.push(
        '  ' + String(r.turnNumber).padStart(2, ' ') + ' | ' +
        cat + ' | ' + orig + ' | ' + pruned + ' | ' + saved + ' | ' + pct + ' | ' + bar
      );
    }

    return lines.join('\n');
  }

  generateSvgChart(width = 600, height = 300) {
    const count = this.turnRecords.length;
    const padding = 40;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    const maxTokens = Math.max(1000, ...this.turnRecords.map(r => r.originalTokens));
    const stepX = count > 1 ? chartWidth / (count - 1) : chartWidth;

    let origPoints = '';
    let prunedPoints = '';

    this.turnRecords.forEach((r, i) => {
      const x = padding + (i * stepX);
      const yOrig = padding + chartHeight - ((r.originalTokens / maxTokens) * chartHeight);
      const yPruned = padding + chartHeight - ((r.prunedTokens / maxTokens) * chartHeight);

      origPoints += x + ',' + yOrig + ' ';
      prunedPoints += x + ',' + yPruned + ' ';
    });

    const svg = [
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + width + ' ' + height + '" width="100%" height="100%">',
      '  <rect width="100%" height="100%" fill="#0d1117"/>',
      '  <text x="20" y="25" fill="#58a6ff" font-family="monospace" font-size="14" font-weight="bold">Symphony Context Pruning Delta (Turns 1-' + count + ')</text>',
      '  <!-- Grid lines -->',
      '  <line x1="' + padding + '" y1="' + padding + '" x2="' + padding + '" y2="' + (height - padding) + '" stroke="#30363d" stroke-width="1"/>',
      '  <line x1="' + padding + '" y1="' + (height - padding) + '" x2="' + (width - padding) + '" y2="' + (height - padding) + '" stroke="#30363d" stroke-width="1"/>',
      '  <!-- Raw Polyline -->',
      '  <polyline fill="none" stroke="#f85149" stroke-width="2" points="' + origPoints.trim() + '"/>',
      '  <!-- Pruned Polyline -->',
      '  <polyline fill="none" stroke="#2ea043" stroke-width="2" points="' + prunedPoints.trim() + '"/>',
      '  <!-- Legend -->',
      '  <circle cx="' + (width - 160) + '" cy="20" r="5" fill="#f85149"/>',
      '  <text x="' + (width - 150) + '" y="24" fill="#8b949e" font-family="monospace" font-size="11">Raw Tokens</text>',
      '  <circle cx="' + (width - 80) + '" cy="20" r="5" fill="#2ea043"/>',
      '  <text x="' + (width - 70) + '" y="24" fill="#8b949e" font-family="monospace" font-size="11">Pruned</text>',
      '</svg>'
    ].join('\n');

    return svg;
  }
}

module.exports = { ContextDeltaVisualizer };
