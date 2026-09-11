const crypto = require('crypto');

class WebhookKeyRotator {
  constructor(initialSecret = 'sec_initial_123') {
    this.primarySecret = initialSecret;
    this.previousSecret = null;
    this.rotationHistory = [
      { secretHash: this.hash(initialSecret), timestamp: new Date().toISOString(), event: 'INITIALIZED' }
    ];
  }

  hash(s) {
    return crypto.createHash('sha256').update(s).digest('hex').slice(0, 16);
  }

  rotateSecret(newSecret) {
    if (!newSecret || newSecret === this.primarySecret) {
      throw new Error('New secret must be non-empty and different from primary');
    }
    this.previousSecret = this.primarySecret;
    this.primarySecret = newSecret;
    this.rotationHistory.push({
      secretHash: this.hash(newSecret),
      timestamp: new Date().toISOString(),
      event: 'ROTATED'
    });
    return {
      primaryHash: this.hash(this.primarySecret),
      previousHash: this.hash(this.previousSecret)
    };
  }

  computeSignature(payload, secret) {
    return crypto.createHmac('sha256', secret).update(payload).digest('hex');
  }

  verifySignature(payload, signature) {
    if (!signature || typeof signature !== 'string') return { valid: false, keyUsed: 'NONE' };
    const bufSig = Buffer.from(signature);

    // Verify against primary secret
    const sigPrimary = this.computeSignature(payload, this.primarySecret);
    const bufPrimary = Buffer.from(sigPrimary);
    if (bufPrimary.length === bufSig.length && crypto.timingSafeEqual(bufPrimary, bufSig)) {
      return { valid: true, keyUsed: 'PRIMARY' };
    }

    // If grace period previous secret exists, verify against it
    if (this.previousSecret) {
      const sigPrev = this.computeSignature(payload, this.previousSecret);
      const bufPrev = Buffer.from(sigPrev);
      if (bufPrev.length === bufSig.length && crypto.timingSafeEqual(bufPrev, bufSig)) {
        return { valid: true, keyUsed: 'PREVIOUS_GRACE_PERIOD' };
      }
    }

    return { valid: false, keyUsed: 'NONE' };
  }
}

module.exports = { WebhookKeyRotator };
