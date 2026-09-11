/**
 * ast_exporter.js - Multi-Format AST Export & Serialization Adapter
 * Exports trimmed AST trees into JSON, clean YAML, markdown outline, and compact digest formats.
 */
class AstMultiExporter {
  constructor(options = {}) {
    this.options = options;
  }

  exportToJson(astNode, pretty = true) {
    return pretty ? JSON.stringify(astNode, null, 2) : JSON.stringify(astNode);
  }

  exportToYaml(astNode, indent = 0) {
    if (!astNode || typeof astNode !== 'object') return '';
    const spaces = ' '.repeat(indent);
    let yaml = '';

    if (astNode.type) yaml += spaces + 'type: ' + astNode.type + '\n';
    if (astNode.name) yaml += spaces + 'name: ' + astNode.name + '\n';
    if (astNode.value !== undefined) yaml += spaces + 'value: ' + JSON.stringify(astNode.value) + '\n';

    if (astNode.children && Array.isArray(astNode.children) && astNode.children.length > 0) {
      yaml += spaces + 'children:\n';
      astNode.children.forEach(child => {
        yaml += spaces + '  -\n' + this.exportToYaml(child, indent + 4);
      });
    }

    return yaml;
  }

  exportToOutline(astNode, depth = 0) {
    if (!astNode || typeof astNode !== 'object') return '';
    const indent = '  '.repeat(depth);
    const label = astNode.name ? astNode.name : (astNode.type || 'Node');
    let outline = indent + '- **[' + (astNode.type || 'Node') + ']** ' + label + '\n';

    if (astNode.children && Array.isArray(astNode.children)) {
      astNode.children.forEach(c => {
        outline += this.exportToOutline(c, depth + 1);
      });
    }

    return outline;
  }

  exportToDigest(astNode) {
    const tokens = [];
    function traverse(node) {
      if (!node) return;
      tokens.push(node.type ? node.type[0].toUpperCase() : 'N');
      if (node.name) tokens.push(':' + node.name);
      if (node.children) {
        tokens.push('(');
        node.children.forEach((c, idx) => {
          if (idx > 0) tokens.push(',');
          traverse(c);
        });
        tokens.push(')');
      }
    }
    traverse(astNode);
    return tokens.join('');
  }

  exportAll(astNode) {
    return {
      timestamp: new Date().toISOString(),
      formats: {
        json: this.exportToJson(astNode, true),
        yaml: this.exportToYaml(astNode),
        outline: this.exportToOutline(astNode),
        digest: this.exportToDigest(astNode)
      }
    };
  }
}

module.exports = { AstMultiExporter };
