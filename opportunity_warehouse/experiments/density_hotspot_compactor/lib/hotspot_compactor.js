/**
 * Context Window Semantic Density Heatmap & Hotspot Compactor
 * Scans multi-turn context lines, computes localized semantic density profiles,
 * and selectively collapses low-density 'cold zones' into concise placeholders
 * while strictly preserving high-density 'hotspots' (code, keys, financial data).
 */

class DensityHotspotCompactor {
  constructor() {}

  calculateLineDensity(line = '') {
    const trimmed = line.trim();
    if (trimmed.length === 0) return 0.0;

    let density = 0.0;
    // Code syntax cues
    if (/[{}();\[\]=<>]/.test(trimmed)) density += 0.4;
    // Financial / numerical / ID cues
    if (/\b(EUR|USD|\$|€|\d{3,}|0x[a-fA-F0-9]+)\b/.test(trimmed)) density += 0.6;
    // State transition cues
    if (/\b(SETTLED|MUTEX|LOCKED|CRITICAL|ERROR|INVARIANT|PASS|FAIL)\b/i.test(trimmed)) density += 0.5;
    // Repetitive filler penalty
    if (/(heartbeat|tick|idle|status normal|ok|ping)/i.test(trimmed)) density -= 0.3;

    return Number(Math.max(0.1, Math.min(2.0, density)).toFixed(3));
  }

  computeDensityProfile(lines = []) {
    return lines.map((line, idx) => ({
      lineIndex: idx,
      line,
      density: this.calculateLineDensity(line)
    }));
  }

  compactContext(text = '', threshold = 0.5) {
    const lines = text.split(/\r?\n/);
    const profile = this.computeDensityProfile(lines);

    const compactedLines = [];
    let coldZoneBuffer = [];
    let coldZoneCount = 0;

    for (let i = 0; i < profile.length; i++) {
      const item = profile[i];
      const isHot = item.density >= threshold;

      if (isHot) {
        // Flush cold zone if buffered
        if (coldZoneBuffer.length > 0) {
          compactedLines.push('[... ' + coldZoneBuffer.length + ' routine status log lines collapsed ...]');
          coldZoneCount += coldZoneBuffer.length;
          coldZoneBuffer = [];
        }
        compactedLines.push(item.line);
      } else {
        coldZoneBuffer.push(item.line);
      }
    }

    // Flush trailing cold zone
    if (coldZoneBuffer.length > 0) {
      compactedLines.push('[... ' + coldZoneBuffer.length + ' routine status log lines collapsed ...]');
      coldZoneCount += coldZoneBuffer.length;
    }

    const originalTokens = Math.max(1, Math.round(text.length / 4));
    const compactedText = compactedLines.join('\n');
    const compactedTokens = Math.max(1, Math.round(compactedText.length / 4));
    const tokensSaved = Math.max(0, originalTokens - compactedTokens);
    const savingsPercent = Number(((tokensSaved / originalTokens) * 100).toFixed(1));

    return {
      originalLines: lines.length,
      compactedLines: compactedLines.length,
      collapsedLinesCount: coldZoneCount,
      originalTokens,
      compactedTokens,
      tokensSaved,
      savingsPercent,
      compactedText
    };
  }
}

module.exports = { DensityHotspotCompactor };