/**
 * PATCH CANDIDATE MANAGER & MINIMIZER
 * 
 * Formal models for Campaigns 031 – 034:
 * - Campaign 031: Patch Candidate Standard Structure
 * - Campaign 032: Patch Size Minimization & Anti-Refactor Filter
 * - Campaign 033: Patch Dependency Classification
 * - Campaign 034: Integration Order Permutation Simulation
 */

const crypto = require('crypto');

class PatchCandidateManager {
  /**
   * Campaign 031: Standard Patch Candidate Structure
   */
  static createPatchCandidate(pkgId, patchSpec) {
    const required = [
      'patch_id', 'target_component', 'why_needed', 'source_defect_or_gap',
      'files_expected', 'minimal_change', 'invariants_affected', 'tests',
      'rollback_strategy', 'risk'
    ];
    for (const f of required) {
      if (!patchSpec[f]) throw new Error(`Patch specification missing required field: ${f}`);
    }

    const payload = JSON.stringify(patchSpec);
    const fingerprint = crypto.createHash('sha256').update(payload).digest('hex');

    return {
      package_id: pkgId,
      ...patchSpec,
      fingerprint,
      certified_windows: false
    };
  }

  /**
   * Campaign 032: Patch Size Minimization & Anti-Refactor
   */
  static evaluatePatchMinimality(diffText) {
    const lines = diffText.split('\n');
    let added = 0;
    let deleted = 0;
    let whitespaceOnly = 0;

    for (const line of lines) {
      if (line.startsWith('+') && !line.startsWith('+++')) added++;
      if (line.startsWith('-') && !line.startsWith('---')) deleted++;
      if (/^[+-]\s*$/.test(line)) whitespaceOnly++;
    }

    // Flag cosmetic / stylistic rewrites
    const isCosmetic = whitespaceOnly > (added + deleted) * 0.5;
    const isMassiveRewrite = added > 500 && deleted > 500;

    return {
      minimal: !isCosmetic && !isMassiveRewrite,
      added_lines: added,
      deleted_lines: deleted,
      code: isCosmetic ? 'COSMETIC_REWRITE_REJECTED' : isMassiveRewrite ? 'MASSIVE_REWRITE_BLOCKED' : 'PATCH_MINIMAL'
    };
  }

  /**
   * Campaign 033: Patch Dependency Classification
   */
  static classifyDependency(patchA, patchB) {
    // If patchB modifies files created by patchA -> REQUIRES
    const sharedFiles = patchA.files_expected.filter(f => patchB.files_expected.includes(f));
    if (sharedFiles.length === 0) return 'INDEPENDENT';

    if (patchB.requires && patchB.requires.includes(patchA.patch_id)) {
      return 'REQUIRES';
    }
    if (patchA.invariants_affected.some(inv => patchB.invariants_affected.includes(inv))) {
      return 'REQUIRES';
    }
    return 'INDEPENDENT';
  }

  /**
   * Campaign 034: Order Permutation Simulation
   */
  static simulateOrderPermutation(orderList, dependencyMap) {
    const installed = new Set();
    for (let i = 0; i < orderList.length; i++) {
      const current = orderList[i];
      const reqs = dependencyMap[current] || [];
      for (const req of reqs) {
        if (!installed.has(req)) {
          return {
            valid: false,
            failing_stage: i,
            violating_patch: current,
            missing_dependency: req,
            reason: `Patch ${current} installed before required dependency ${req}`
          };
        }
      }
      installed.add(current);
    }
    return { valid: true, installed_count: installed.size };
  }
}

module.exports = { PatchCandidateManager };
