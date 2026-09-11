// SVG Terminal Card & Animation Generator
// Renders high-fidelity, zero-dependency SVG terminal demo cards for developer tools.
// Zero external dependencies.

class TerminalAnimator {
  static generateCardSVG({
    title = 'agent-context-trimmer v1.0.0',
    command = 'npx agent-context-trimmer --audit',
    lines = [],
    width = 720,
    headerBg = '#161b22',
    bg = '#0d1117',
    textColor = '#c9d1d9',
    accentColor = '#2ea043'
  } = {}) {
    const lineHeight = 20;
    const padding = 24;
    const headerHeight = 42;
    const totalHeight = headerHeight + padding * 2 + lines.length * lineHeight;

    const escapeXml = (unsafe) => {
      return String(unsafe)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
    };

    const textElements = lines.map((line, idx) => {
      const y = headerHeight + padding + (idx + 1) * lineHeight;
      let fill = textColor;
      if (line.includes('PASS') || line.includes('SAVINGS') || line.includes('✔')) fill = accentColor;
      else if (line.includes('WARNING') || line.includes('BLOAT') || line.includes('FAIL')) fill = '#d29922';
      else if (line.startsWith('$') || line.startsWith('===')) fill = '#58a6ff';

      return `<text x="${padding}" y="${y}" fill="${fill}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="13">${escapeXml(line)}</text>`;
    }).join('\n    ');

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${totalHeight}" width="${width}" height="${totalHeight}">
  <defs>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000000" flood-opacity="0.5"/>
    </filter>
  </defs>
  <rect width="${width}" height="${totalHeight}" rx="10" fill="${bg}" stroke="#30363d" stroke-width="1" filter="url(#shadow)"/>
  <path d="M 0 10 C 0 4.477 4.477 0 10 0 L ${width - 10} 0 C ${width - 4.477} 0 ${width} 4.477 ${width} 10 L ${width} ${headerHeight} L 0 ${headerHeight} Z" fill="${headerBg}"/>
  <line x1="0" y1="${headerHeight}" x2="${width}" y2="${headerHeight}" stroke="#30363d" stroke-width="1"/>
  
  <!-- Window Controls -->
  <circle cx="20" cy="21" r="6" fill="#ff5f56"/>
  <circle cx="40" cy="21" r="6" fill="#ffbd2e"/>
  <circle cx="60" cy="21" r="6" fill="#27c93f"/>
  
  <!-- Header Title -->
  <text x="${width / 2}" y="25" fill="#8b949e" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="12" font-weight="600" text-anchor="middle">${escapeXml(title)}</text>
  
  <!-- Terminal Content -->
  <g>
    ${textElements}
  </g>
</svg>`;
  }
}

module.exports = { TerminalAnimator };
