/**
 * rule_diff.js - Semantic Rule Version Diff Engine & Compatibility Analyzer
 * Compares rule sets across versions, detects breaking changes, and calculates compatibility scores.
 */
class RuleDiffEngine {
  constructor(options = {}) {
    this.options = {
      strictMode: options.strictMode || false,
      weights: {
        removedErrorRule: 25,
        removedWarningRule: 10,
        severityEscalated: 20,
        actionEscalated: 15,
        propertyModified: 5,
        ...options.weights
      }
    };
  }

  normalizeRule(rule) {
    if (typeof rule === 'string') {
      return { id: rule, name: rule, pattern: rule, severity: 'warning', action: 'trim' };
    }
    return {
      id: rule.id || rule.name || 'unnamed_rule',
      name: rule.name || rule.id || 'Unnamed Rule',
      pattern: rule.pattern || '',
      severity: rule.severity || 'warning',
      action: rule.action || 'trim',
      description: rule.description || ''
    };
  }

  compare(oldRules = [], newRules = []) {
    const oldNorm = oldRules.map(r => this.normalizeRule(r));
    const newNorm = newRules.map(r => this.normalizeRule(r));

    const oldMap = new Map(oldNorm.map(r => [r.id, r]));
    const newMap = new Map(newNorm.map(r => [r.id, r]));

    const added = [];
    const removed = [];
    const modified = [];
    const unchanged = [];
    const breakingChanges = [];

    // Check additions and modifications
    for (const [id, newRule] of newMap.entries()) {
      if (!oldMap.has(id)) {
        added.push(newRule);
      } else {
        const oldRule = oldMap.get(id);
        const changes = {};
        let isModified = false;

        ['name', 'pattern', 'severity', 'action', 'description'].forEach(prop => {
          if (oldRule[prop] !== newRule[prop]) {
            changes[prop] = { from: oldRule[prop], to: newRule[prop] };
            isModified = true;
          }
        });

        if (isModified) {
          const modEntry = { id, oldRule, newRule, changes };
          modified.push(modEntry);

          // Check if breaking
          if (oldRule.severity === 'warning' && newRule.severity === 'error') {
            breakingChanges.push({
              type: 'SEVERITY_ESCALATION',
              id,
              description: 'Rule ' + id + ' severity escalated from warning to error'
            });
          }
          if (oldRule.action !== 'drop' && newRule.action === 'drop') {
            breakingChanges.push({
              type: 'ACTION_ESCALATION',
              id,
              description: 'Rule ' + id + ' action escalated from ' + oldRule.action + ' to drop'
            });
          }
        } else {
          unchanged.push(newRule);
        }
      }
    }

    // Check removals
    for (const [id, oldRule] of oldMap.entries()) {
      if (!newMap.has(id)) {
        removed.push(oldRule);
        if (oldRule.severity === 'error') {
          breakingChanges.push({
            type: 'CRITICAL_RULE_REMOVAL',
            id,
            description: 'Error-level rule ' + id + ' was removed'
          });
        }
      }
    }

    // Calculate score
    let penalty = 0;
    breakingChanges.forEach(b => {
      if (b.type === 'CRITICAL_RULE_REMOVAL') penalty += this.options.weights.removedErrorRule;
      else if (b.type === 'SEVERITY_ESCALATION') penalty += this.options.weights.severityEscalated;
      else if (b.type === 'ACTION_ESCALATION') penalty += this.options.weights.actionEscalated;
    });
    modified.forEach(m => {
      penalty += Object.keys(m.changes).length * this.options.weights.propertyModified;
    });

    const compatibilityScore = Math.max(0, Math.min(100, 100 - penalty));
    const isCompatible = breakingChanges.length === 0 && compatibilityScore >= 70;

    return {
      timestamp: new Date().toISOString(),
      summary: {
        totalOld: oldNorm.length,
        totalNew: newNorm.length,
        addedCount: added.length,
        removedCount: removed.length,
        modifiedCount: modified.length,
        unchangedCount: unchanged.length,
        breakingCount: breakingChanges.length,
        compatibilityScore,
        isCompatible
      },
      added,
      removed,
      modified,
      unchanged,
      breakingChanges
    };
  }

  generateMarkdownReport(diffResult, title = 'Rule Version Compatibility Report') {
    const s = diffResult.summary;
    const statusBadge = s.isCompatible ? 'COMPATIBLE' : 'BREAKING_CHANGES_DETECTED';
    let md = '# ' + title + '\n\n';
    md += '- **Status**: ' + statusBadge + '\n';
    md += '- **Compatibility Score**: ' + s.compatibilityScore + '/100\n';
    md += '- **Changes**: +' + s.addedCount + ' added, -' + s.removedCount + ' removed, ~' + s.modifiedCount + ' modified, =' + s.unchangedCount + ' unchanged\n';
    md += '- **Breaking Issues**: ' + s.breakingCount + '\n\n';

    if (diffResult.breakingChanges.length > 0) {
      md += '### Breaking Changes\n';
      diffResult.breakingChanges.forEach(b => {
        md += '- **[' + b.type + ']** ' + b.description + '\n';
      });
      md += '\n';
    }

    if (diffResult.added.length > 0) {
      md += '### Added Rules (+' + diffResult.added.length + ')\n';
      diffResult.added.forEach(r => {
        md += '- `' + r.id + '` (' + r.severity + '): ' + r.name + '\n';
      });
      md += '\n';
    }

    if (diffResult.modified.length > 0) {
      md += '### Modified Rules (~' + diffResult.modified.length + ')\n';
      diffResult.modified.forEach(m => {
        const detail = Object.keys(m.changes).map(k => k + ' (' + m.changes[k].from + ' -> ' + m.changes[k].to + ')').join(', ');
        md += '- `' + m.id + '`: ' + detail + '\n';
      });
      md += '\n';
    }

    return md;
  }
}

module.exports = { RuleDiffEngine };
