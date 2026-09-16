// PolicyValidator.js — Validates LONG_RUN_POLICY.yaml invariants
const fs = require('fs');
const path = require('path');

class PolicyValidator {
  constructor(policyPath) {
    this.policyPath = policyPath;
    this.policy = null;
  }

  load() {
    if (!fs.existsSync(this.policyPath)) {
      throw new Error('LONG_RUN_POLICY file not found at: ' + this.policyPath);
    }
    const raw = fs.readFileSync(this.policyPath, 'utf8');
    this.policy = this.parseSimpleYaml(raw);
    return this.policy;
  }

  parseSimpleYaml(raw) {
    const lines = raw.split('\n');
    const res = {};
    let currentSection = null;

    for (let line of lines) {
      line = line.trim();
      if (!line || line.startsWith('#')) continue;

      if (line.endsWith(':') && !line.includes(' -')) {
        currentSection = line.slice(0, -1).trim();
        res[currentSection] = {};
        continue;
      }

      if (line.startsWith('- ')) {
        if (currentSection && !Array.isArray(res[currentSection])) {
          res[currentSection] = [];
        }
        if (currentSection) {
          res[currentSection].push(line.slice(2).trim().replace(/^["']|["']$/g, ''));
        }
        continue;
      }

      const colIdx = line.indexOf(':');
      if (colIdx !== -1) {
        const key = line.slice(0, colIdx).trim();
        let val = line.slice(colIdx + 1).trim().replace(/^["']|["']$/g, '');
        if (val === 'true') val = true;
        else if (val === 'false') val = false;
        else if (/^\d+$/.test(val)) val = parseInt(val, 10);

        if (currentSection && typeof res[currentSection] === 'object') {
          res[currentSection][key] = val;
        } else {
          res[key] = val;
        }
      }
    }
    return res;
  }

  validate(envContext = {}) {
    if (!this.policy) this.load();

    const findings = [];
    const core = this.policy.core_continuation_contract || {};
    const flags = this.policy.operational_flags || {};

    if (core.long_run_by_default !== true) {
      findings.push('VIOLATION: core_continuation_contract.long_run_by_default must be true');
    }
    if (typeof core.frontier_low_water !== 'number' || core.frontier_low_water < 4) {
      findings.push('VIOLATION: core_continuation_contract.frontier_low_water must be >= 4');
    }
    if (core.worker_global_completion_authority !== false) {
      findings.push('VIOLATION: core_continuation_contract.worker_global_completion_authority must be false');
    }
    if (core.completion_governor_required !== true) {
      findings.push('VIOLATION: core_continuation_contract.completion_governor_required must be true');
    }
    if (core.capacity_end_state !== 'PAUSED_CAPACITY') {
      findings.push('VIOLATION: core_continuation_contract.capacity_end_state must be PAUSED_CAPACITY');
    }

    if (flags.autonomous_spend_limit_eur !== 0) {
      findings.push('VIOLATION: operational_flags.autonomous_spend_limit_eur must be 0');
    }
    if (flags.real_trading_allowed !== false) {
      findings.push('VIOLATION: operational_flags.real_trading_allowed must be false');
    }
    if (flags.wallet_signing_allowed !== false) {
      findings.push('VIOLATION: operational_flags.wallet_signing_allowed must be false');
    }
    if (flags.mac_host_access_allowed !== false) {
      findings.push('VIOLATION: operational_flags.mac_host_access_allowed must be false');
    }
    if (flags.universux_touch_allowed !== false) {
      findings.push('VIOLATION: operational_flags.universux_touch_allowed must be false');
    }

    return {
      valid: findings.length === 0,
      policy_id: this.policy.meta ? this.policy.meta.policy_id : 'UNKNOWN',
      policy_version: this.policy.meta ? this.policy.meta.policy_version : 'UNKNOWN',
      findings
    };
  }
}

module.exports = { PolicyValidator };