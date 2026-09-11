/**
 * ast_patcher.js - AST Diff-Patch & Incremental Update Applicator
 * Applies targeted AST node replacements into existing code trees without full regeneration.
 */
class AstDiffPatcher {
  constructor() {}

  findNode(root, targetName) {
    if (!root || typeof root !== 'object') return null;
    if (root.name === targetName) return root;

    if (Array.isArray(root.children)) {
      for (const child of root.children) {
        const found = this.findNode(child, targetName);
        if (found) return found;
      }
    }
    return null;
  }

  applyPatch(targetTree, patchNode) {
    if (!targetTree || !patchNode || !patchNode.targetName) {
      return { success: false, error: 'Invalid patch specification: targetName required' };
    }

    let replaced = false;

    const traverseAndReplace = (node) => {
      if (!node || typeof node !== 'object') return;

      if (Array.isArray(node.children)) {
        for (let i = 0; i < node.children.length; i++) {
          const child = node.children[i];
          if (child.name === patchNode.targetName) {
            // Replace node with patch contents
            node.children[i] = {
              ...child,
              ...patchNode.replacement,
              name: patchNode.replacement.name || child.name,
              patchedAt: new Date().toISOString()
            };
            replaced = true;
            return;
          }
          traverseAndReplace(child);
        }
      }
    };

    traverseAndReplace(targetTree);

    if (!replaced) {
      return { success: false, error: 'Target node "' + patchNode.targetName + '" not found in tree' };
    }

    return {
      success: true,
      targetName: patchNode.targetName,
      patchedTree: targetTree,
      timestamp: new Date().toISOString()
    };
  }
}

module.exports = { AstDiffPatcher };
