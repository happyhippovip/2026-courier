class AstReconstructor {
  constructor() {}

  parseToAst(promptText) {
    if (!promptText) return { type: 'Root', children: [] };
    const lines = promptText.split('\n');
    const nodes = [];
    let currentBlock = null;

    for (const line of lines) {
      if (line.startsWith('```')) {
        if (currentBlock) {
          currentBlock.lines.push(line);
          nodes.push(currentBlock);
          currentBlock = null;
        } else {
          currentBlock = { type: 'CodeBlock', lines: [line] };
        }
      } else if (currentBlock) {
        currentBlock.lines.push(line);
      } else if (line.startsWith('#')) {
        nodes.push({ type: 'Header', content: line.trim() });
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        nodes.push({ type: 'ListItem', content: line.trim() });
      } else if (line.trim().length > 0) {
        nodes.push({ type: 'Paragraph', content: line.trim() });
      }
    }
    if (currentBlock) nodes.push(currentBlock);
    return { type: 'Root', children: nodes };
  }

  reconstructMarkdown(ast) {
    if (!ast || !ast.children) return '';
    const output = [];

    for (const node of ast.children) {
      if (node.type === 'Header') {
        output.push('\n' + node.content + '\n');
      } else if (node.type === 'ListItem') {
        output.push(node.content);
      } else if (node.type === 'Paragraph') {
        output.push(node.content + '\n');
      } else if (node.type === 'CodeBlock') {
        output.push(node.lines.join('\n') + '\n');
      }
    }
    return output.join('\n').trim();
  }

  verifyLosslessDirectives(originalPrompt, reconstructedPrompt) {
    const extractDirectives = (txt) => {
      const matches = txt.match(/(?:MUST|NEVER|ALWAYS|REQUIRED|FORBIDDEN)[^.\n]+/g) || [];
      return matches.map(m => m.trim().toUpperCase());
    };

    const origDirectives = extractDirectives(originalPrompt);
    const reconDirectives = extractDirectives(reconstructedPrompt);

    const missing = origDirectives.filter(d => !reconDirectives.includes(d));
    return {
      lossless: missing.length === 0,
      totalOriginalDirectives: origDirectives.length,
      totalReconstructedDirectives: reconDirectives.length,
      missingDirectives: missing
    };
  }
}

module.exports = { AstReconstructor };
