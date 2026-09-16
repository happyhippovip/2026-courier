// 7-Level Capability Lattice with Strict Ceilings
const CAPABILITY_LATTICE = Object.freeze({
  READ_ONLY: 1,
  WORKSPACE_WRITE: 2,
  EXTERNAL_FS: 3,
  NETWORK_INSPECT: 4,
  NETWORK_CALL: 5,
  SECRETS_ACCESS: 6,
  FINANCIAL_LIABILITY: 7
});

class CapabilityEngine {
  static getLevel(capName) {
    const map = {
      'READ_ONLY': 1, 'FILE_READ': 1, 'STATUS_CHECK': 1,
      'WORKSPACE_WRITE': 2, 'SCRATCH_WRITE': 2, 'LOCAL_TEST': 2,
      'EXTERNAL_FS_WRITE': 3, 'SYSTEM_CONFIG': 3,
      'NETWORK_INSPECT': 4,
      'NETWORK_CALL': 5,
      'SECRETS_ACCESS': 6,
      'FINANCIAL_LIABILITY': 7, 'SPEND_EUR': 7, 'REAL_TRADE': 7, 'WALLET_SIGN': 7
    };
    return map[(capName || '').toUpperCase()] || 99;
  }

  static authorize(requestedCap, maxAllowed = CAPABILITY_LATTICE.WORKSPACE_WRITE) {
    const lvl = CapabilityEngine.getLevel(requestedCap);
    if (lvl > maxAllowed) {
      return {
        allowed: false,
        required_level: lvl,
        max_allowed: maxAllowed,
        requires_human_gate: lvl >= CAPABILITY_LATTICE.SECRETS_ACCESS,
        reason: `Capability '${requestedCap}' (${lvl}) exceeds ceiling ${maxAllowed}`
      };
    }
    return { allowed: true, required_level: lvl, max_allowed: maxAllowed, requires_human_gate: false };
  }
}

module.exports = { CapabilityEngine, CAPABILITY_LATTICE };
