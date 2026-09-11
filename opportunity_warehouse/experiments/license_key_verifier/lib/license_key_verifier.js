// Offline / Online License Key Verifier
// Formats: GUMROAD-KEY-XXXX-XXXX-XXXX-XXXX
// Zero external dependencies.

const crypto = require('crypto');

class LicenseKeyVerifier {
  constructor({ salt = 'SYMPHONY_LICENSE_SALT_2026' } = {}) {
    this.salt = salt;
  }

  generateKey({ orderId, customerEmail, tier = 'STANDARD' }) {
    if (!orderId || !customerEmail) {
      throw new Error('[LICENSE_ERROR] orderId and customerEmail are required');
    }

    const raw = `${orderId}:${customerEmail}:${tier}:${this.salt}`;
    const hash = crypto.createHash('sha256').update(raw).digest('hex').toUpperCase();
    
    // Group into 4x4 characters
    const part1 = hash.slice(0, 4);
    const part2 = hash.slice(4, 8);
    const part3 = hash.slice(8, 12);
    const part4 = hash.slice(12, 16);

    return `SYM-${tier}-${part1}-${part2}-${part3}-${part4}`;
  }

  verifyKey({ licenseKey, orderId, customerEmail, tier = 'STANDARD' }) {
    if (!licenseKey || typeof licenseKey !== 'string') return false;
    const expected = this.generateKey({ orderId, customerEmail, tier });
    return licenseKey === expected;
  }
}

module.exports = { LicenseKeyVerifier };
