module.exports = function hierarchicalScopeConflict(scopeA, scopeB) {
    const normA = path.normalize(scopeA).replace(/\\/g, '/').replace(/\/$/, '') + '/';
    const normB = path.normalize(scopeB).replace(/\\/g, '/').replace(/\/$/, '') + '/';
    if (normA === normB) return true;
    if (normA.startsWith(normB) || normB.startsWith(normA)) return true;
    return false;
  };
