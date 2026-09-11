class TuiTreeVisualizer {
  constructor() {}

  renderTree(node, prefix = '', isTail = true) {
    if (!node) return '';

    const branch = isTail ? '└── ' : '├── ';
    const statusIcon = node.pruned ? '✂ [PRUNED]' : '✔ [KEPT]';
    const weightLabel = node.tokens ? ` (${node.tokens} tokens)` : '';
    let result = prefix + branch + `${node.name} ${statusIcon}${weightLabel}\n`;

    if (node.children && node.children.length > 0) {
      for (let i = 0; i < node.children.length; i++) {
        const child = node.children[i];
        const isLast = i === node.children.length - 1;
        const nextPrefix = prefix + (isTail ? '    ' : '│   ');
        result += this.renderTree(child, nextPrefix, isLast);
      }
    }

    return result;
  }

  generateReport(rootNode) {
    let totalTokens = 0;
    let prunedTokens = 0;

    const traverse = (n) => {
      if (!n) return;
      const t = n.tokens || 0;
      totalTokens += t;
      if (n.pruned) prunedTokens += t;
      if (n.children) n.children.forEach(traverse);
    };

    traverse(rootNode);

    const keptTokens = Math.max(0, totalTokens - prunedTokens);
    const reductionPct = totalTokens > 0 ? Number(((prunedTokens / totalTokens) * 100).toFixed(2)) : 0;

    const treeGraph = this.renderTree(rootNode);

    return {
      treeGraph,
      metrics: {
        totalTokens,
        prunedTokens,
        keptTokens,
        reductionPct
      }
    };
  }
}

module.exports = { TuiTreeVisualizer };
