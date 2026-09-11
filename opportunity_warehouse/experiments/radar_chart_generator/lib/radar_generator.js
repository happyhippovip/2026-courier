class RadarChartGenerator {
  constructor(options = {}) {
    this.width = options.width || 500;
    this.height = options.height || 500;
    this.center = { x: this.width / 2, y: this.height / 2 };
    this.radius = options.radius || 180;
  }

  generateSvg(metrics = {}) {
    // Expected metrics: { tokenSavings: 0-100, latencySpeedup: 0-100, memoryEfficiency: 0-100, rulePreservation: 0-100, costEfficiency: 0-100 }
    const keys = ['Token Reduction', 'Latency Speedup', 'Memory Efficiency', 'Rule Preservation', 'Cost Efficiency'];
    const values = [
      metrics.tokenSavings || 85,
      metrics.latencySpeedup || 95,
      metrics.memoryEfficiency || 90,
      metrics.rulePreservation || 100,
      metrics.costEfficiency || 92
    ];

    const angleStep = (Math.PI * 2) / keys.length;
    let polygonPoints = [];
    let axisLines = [];
    let labels = [];

    for (let i = 0; i < keys.length; i++) {
      const angle = i * angleStep - Math.PI / 2;
      const xMax = this.center.x + this.radius * Math.cos(angle);
      const yMax = this.center.y + this.radius * Math.sin(angle);
      axisLines.push(`<line x1="${this.center.x}" y1="${this.center.y}" x2="${xMax.toFixed(2)}" y2="${yMax.toFixed(2)}" stroke="#374151" stroke-width="1.5" />`);

      // Label positioning
      const labelDist = this.radius + 35;
      const lx = this.center.x + labelDist * Math.cos(angle);
      const ly = this.center.y + labelDist * Math.sin(angle);
      labels.push(`<text x="${lx.toFixed(2)}" y="${ly.toFixed(2)}" fill="#9CA3AF" font-family="system-ui, sans-serif" font-size="12" text-anchor="middle" dominant-baseline="middle">${keys[i]} (${values[i]}%)</text>`);

      // Data point
      const r = (values[i] / 100) * this.radius;
      const px = this.center.x + r * Math.cos(angle);
      const py = this.center.y + r * Math.sin(angle);
      polygonPoints.push(`${px.toFixed(2)},${py.toFixed(2)}`);
    }

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${this.width} ${this.height}" width="${this.width}" height="${this.height}" style="background-color: #111827; border-radius: 8px;">
  <title>agent-context-trimmer Performance Radar</title>
  <defs>
    <linearGradient id="polyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#10B981" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="#3B82F6" stop-opacity="0.4"/>
    </linearGradient>
  </defs>

  <!-- Background Web Rings -->
  <circle cx="${this.center.x}" cy="${this.center.y}" r="${(this.radius * 0.25).toFixed(2)}" fill="none" stroke="#1F2937" stroke-width="1" />
  <circle cx="${this.center.x}" cy="${this.center.y}" r="${(this.radius * 0.50).toFixed(2)}" fill="none" stroke="#1F2937" stroke-width="1" />
  <circle cx="${this.center.x}" cy="${this.center.y}" r="${(this.radius * 0.75).toFixed(2)}" fill="none" stroke="#1F2937" stroke-width="1" />
  <circle cx="${this.center.x}" cy="${this.center.y}" r="${this.radius}" fill="none" stroke="#374151" stroke-width="1.5" />

  <!-- Axes -->
  ${axisLines.join('\n  ')}

  <!-- Data Polygon -->
  <polygon points="${polygonPoints.join(' ')}" fill="url(#polyGrad)" stroke="#10B981" stroke-width="2.5" />

  <!-- Labels -->
  ${labels.join('\n  ')}
</svg>`;
  }
}

module.exports = { RadarChartGenerator };
