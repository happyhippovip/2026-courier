/**
 * Semantic Markdown Table & Tabular Context Compactor
 * Optimizes Markdown tables by eliminating padding whitespace, dropping redundant
 * uniform columns, and minifying delimiter rows while maintaining semantic readability.
 */

class TabularContextCompactor {
  constructor() {}

  parseTable(markdownTable = '') {
    const lines = markdownTable.trim().split('\n').filter(l => l.trim().startsWith('|'));
    if (lines.length < 2) return null;

    const parseRow = line => line
      .split('|')
      .slice(1, -1)
      .map(cell => cell.trim());

    const headers = parseRow(lines[0]);
    const alignLine = lines[1];
    const dataRows = lines.slice(2).map(parseRow);

    return {
      headers,
      alignLine,
      dataRows
    };
  }

  stripPadding(markdownTable = '') {
    const lines = markdownTable.trim().split('\n');
    const strippedLines = lines.map(line => {
      const trimmed = line.trim();
      if (!trimmed.startsWith('|')) return line;
      const cells = trimmed.split('|').slice(1, -1).map(c => c.trim());
      return '|' + cells.join('|') + '|';
    });
    return strippedLines.join('\n');
  }

  pruneRedundantColumns(parsedTable, options = {}) {
    if (!parsedTable || parsedTable.dataRows.length === 0) return parsedTable;

    const colCount = parsedTable.headers.length;
    const keepColIndices = [];

    for (let c = 0; c < colCount; c++) {
      const header = parsedTable.headers[c];
      const values = parsedTable.dataRows.map(r => r[c] || '');

      // Check if all values are identical or empty
      const firstVal = values[0];
      const allIdentical = values.every(v => v === firstVal);
      const isUniformDefault = allIdentical && (firstVal === 'OK' || firstVal === 'N/A' || firstVal === '' || firstVal === 'true');

      if (!isUniformDefault || options.preserveAllColumns) {
        keepColIndices.push(c);
      }
    }

    const newHeaders = keepColIndices.map(i => parsedTable.headers[i]);
    const newRows = parsedTable.dataRows.map(row => keepColIndices.map(i => row[i] || ''));

    return {
      headers: newHeaders,
      dataRows: newRows,
      droppedCount: colCount - keepColIndices.length
    };
  }

  compactTable(markdownTable = '', options = {}) {
    const parsed = this.parseTable(markdownTable);
    if (!parsed) return { compactedText: markdownTable, tokensSaved: 0 };

    const pruned = this.pruneRedundantColumns(parsed, options);

    // Build unpadded minimal markdown table
    const headerLine = '|' + pruned.headers.join('|') + '|';
    const alignLine = '|' + pruned.headers.map(() => '---').join('|') + '|';
    const dataLines = pruned.dataRows.map(r => '|' + r.join('|') + '|');

    const resultTable = [headerLine, alignLine, ...dataLines].join('\n');

    const origTokens = Math.max(1, Math.round(markdownTable.length / 4));
    const finalTokens = Math.max(1, Math.round(resultTable.length / 4));

    return {
      originalTokens: origTokens,
      finalTokens: finalTokens,
      tokensSaved: Math.max(0, origTokens - finalTokens),
      savingsPercent: Number((((origTokens - finalTokens) / origTokens) * 100).toFixed(1)),
      columnsRetained: pruned.headers.length,
      columnsDropped: pruned.droppedCount,
      compactedTable: resultTable
    };
  }
}

module.exports = { TabularContextCompactor };
