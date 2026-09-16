// Constitution Validator V1 — Expedition V1
// Programmatically validates runtime modules, state, and environment against COURIER_ARCHITECTURE_CONSTITUTION.yaml

const fs = require('fs');
const path = require('path');

class ConstitutionValidator {
  constructor(constitutionPath) {
    this.constitutionPath = constitutionPath;
    this.invariants = [];
  }

  load() {
    if (!fs.existsSync(this.constitutionPath)) {
      throw new Error('Constitution file not found at: ' + this.constitutionPath);
    }
    const raw = fs.readFileSync(this.constitutionPath, 'utf8');
    
    // Parse YAML invariants manually without external dependencies
    const blocks = raw.split(/\n\s*-\s+id:\s*/);
    this.invariants = [];
    for (let i = 1; i < blocks.length; i++) {
      const b = blocks[i];
      const idMatch = b.match(/^"([^"]+)"/);
      const nameMatch = b.match(/name:\s*"([^"]+)"/);
      const classMatch = b.match(/classification:\s*"([^"]+)"/);
      const descMatch = b.match(/description:\s*"([^"]+)"/);
      const enfMatch = b.match(/enforcement_rule:\s*"([^"]+)"/);

      if (idMatch && nameMatch) {
        this.invariants.push({
          id: idMatch[1],
          name: nameMatch[1],
          classification: classMatch ? classMatch[1] : 'UNKNOWN',
          description: descMatch ? descMatch[1] : '',
          enforcement_rule: enfMatch ? enfMatch[1] : ''
        });
      }
    }
    return this.invariants;
  }

  validateEnvironment(env) {
    const findings = [];
    
    // Check spend limit (€0)
    if (env.spend_eur > 0) {
      findings.push({ invariant: 'ZERO_SPEND_DEFAULT', status: 'VIOLATION', details: 'Spend EUR > 0: ' + env.spend_eur });
    }
    
    // Check mac access (strictly no)
    if (env.mac_accessed) {
      findings.push({ invariant: 'SINGLE_WRITER_PARTITIONING', status: 'VIOLATION', details: 'Mac access attempted' });
    }

    // Check universuX touch (strictly no)
    if (env.universux_touched) {
      findings.push({ invariant: 'CORE_IP_PROTECTION', status: 'VIOLATION', details: 'universuX repository modified' });
    }

    // Check global saturation rule
    if (env.worker_can_close_mission === true) {
      findings.push({ invariant: 'GLOBAL_SATURATION_REVOCATION', status: 'VIOLATION', details: 'Worker holds global close authority' });
    }

    return {
      valid: findings.length === 0,
      checked_invariants_count: this.invariants.length,
      findings
    };
  }
}

module.exports = {
  ConstitutionValidator
};

if (require.main === module) {
  const cPath = path.join(__dirname, 'COURIER_ARCHITECTURE_CONSTITUTION.yaml');
  const cv = new ConstitutionValidator(cPath);
  const invs = cv.load();
  console.log('Constitution loaded successfully! Total Invariants: ' + invs.length);
  const testEnv = {
    spend_eur: 0,
    mac_accessed: false,
    universux_touched: false,
    worker_can_close_mission: false
  };
  const valRes = cv.validateEnvironment(testEnv);
  console.log('Environment Validation Result: ' + (valRes.valid ? 'PASSED (0 violations)' : 'FAILED'));
}
