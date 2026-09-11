function extractCodeBlocks(markdownText) {
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const blocks = [];
  let match;

  while ((match = codeBlockRegex.exec(markdownText)) !== null) {
    blocks.push({
      language: match[1] || 'text',
      code: match[2],
      index: match.index
    });
  }

  return blocks;
}

function checkDelimiterBalance(codeText) {
  const stack = [];
  const pairs = { '}': '{', ')': '(', ']': '[' };
  const opens = new Set(['{', '(', '[']);
  const closes = new Set(['}', ')', ']']);

  for (let i = 0; i < codeText.length; i++) {
    const char = codeText[i];
    if (opens.has(char)) {
      stack.push({ char, index: i });
    } else if (closes.has(char)) {
      if (stack.length === 0 || stack[stack.length - 1].char !== pairs[char]) {
        return { is_balanced: false, error: `Unmatched closing delimiter '${char}' at index ${i}` };
      }
      stack.pop();
    }
  }

  if (stack.length > 0) {
    const unclosed = stack.pop();
    return { is_balanced: false, error: `Unclosed delimiter '${unclosed.char}' at index ${unclosed.index}` };
  }

  return { is_balanced: true };
}

function validateMarkdownCodeBlocks(markdownText) {
  const blocks = extractCodeBlocks(markdownText);
  const results = [];
  let errorCount = 0;

  for (let idx = 0; idx < blocks.length; idx++) {
    const b = blocks[idx];
    const balance = checkDelimiterBalance(b.code);
    if (!balance.is_balanced) {
      errorCount++;
      results.push({
        block_index: idx,
        language: b.language,
        status: 'SYNTAX_ERROR',
        error: balance.error
      });
    } else {
      results.push({
        block_index: idx,
        language: b.language,
        status: 'VALID'
      });
    }
  }

  return {
    total_blocks: blocks.length,
    valid_blocks: blocks.length - errorCount,
    error_count: errorCount,
    blocks: results,
    scanned_at: new Date().toISOString()
  };
}

module.exports = { extractCodeBlocks, checkDelimiterBalance, validateMarkdownCodeBlocks };
