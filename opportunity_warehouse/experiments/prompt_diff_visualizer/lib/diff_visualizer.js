function computeLineDiff(originalText, optimizedText) {
  const origLines = originalText.split('\n');
  const optLines = optimizedText.split('\n');
  const diffEntries = [];

  let i = 0;
  let j = 0;

  while (i < origLines.length || j < optLines.length) {
    if (i < origLines.length && j < optLines.length && origLines[i] === optLines[j]) {
      diffEntries.push({ type: 'UNCHANGED', text: origLines[i] });
      i++;
      j++;
    } else if (i < origLines.length && (j >= optLines.length || !optLines.includes(origLines[i]))) {
      diffEntries.push({ type: 'REMOVED', text: origLines[i] });
      i++;
    } else if (j < optLines.length) {
      diffEntries.push({ type: 'ADDED', text: optLines[j] });
      j++;
    }
  }

  return diffEntries;
}

function renderDiffHtml(diffEntries, metadata = {}) {
  const title = metadata.title || 'Context Compression Diff';
  const tokenSavings = metadata.tokenSavings || '-43.8%';

  const rows = diffEntries.map(e => {
    let bg = '#ffffff';
    let sign = '&nbsp;';
    let color = '#24292f';

    if (e.type === 'REMOVED') {
      bg = '#ffebe9';
      sign = '-';
      color = '#cf222e';
    } else if (e.type === 'ADDED') {
      bg = '#dafbe1';
      sign = '+';
      color = '#1a7f37';
    }

    return `<div style="display: flex; background: ${bg}; color: ${color}; font-family: monospace; font-size: 13px; line-height: 20px; padding: 2px 8px;">
      <span style="width: 24px; user-select: none; color: #8c959f;">${sign}</span>
      <span style="white-space: pre-wrap;">${e.text.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</span>
    </div>`;
  }).join('\n');

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; margin: 0; }
    .diff-container { max-width: 800px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }
    .header { padding: 16px; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }
    .header h2 { margin: 0; font-size: 16px; color: #58a6ff; }
    .badge { background: #238636; color: #fff; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; }
  </style>
</head>
<body>
  <div class="diff-container">
    <div class="header">
      <h2>${title}</h2>
      <span class="badge">Savings: ${tokenSavings}</span>
    </div>
    <div style="background: #ffffff; color: #24292f;">
      ${rows}
    </div>
  </div>
</body>
</html>`;
}

module.exports = { computeLineDiff, renderDiffHtml };
