// M2M Agentic Checkout & License Token Validator
// Zero external dependencies.

const crypto = require('crypto');

class M2MCommerceValidator {
  constructor(secretKey = 'SYMPHONY_INTERNAL_SIGNING_KEY_OFFLINE') {
    this.secretKey = secretKey;
    this.issuedLicenses = new Map();
  }

  validateQuoteRequest({ productId, agentPublicKey, maxBudgetEur, availableProducts = {} }) {
    if (!productId || typeof productId !== 'string') {
      throw new Error('[M2M_ERROR] productId is required');
    }
    if (!agentPublicKey || typeof agentPublicKey !== 'string') {
      throw new Error('[M2M_ERROR] agentPublicKey is required');
    }
    if (typeof maxBudgetEur !== 'number' || maxBudgetEur <= 0) {
      throw new Error('[M2M_ERROR] maxBudgetEur must be positive number');
    }

    const price = availableProducts[productId];
    if (price === undefined) {
      throw new Error(`[M2M_ERROR] Product '${productId}' not found in catalog`);
    }

    if (maxBudgetEur < price) {
      throw new Error(`[M2M_ERROR] Insufficient agent budget: required €${price}, max €${maxBudgetEur}`);
    }

    const quoteId = `QUOTE-${Date.now()}-${crypto.randomBytes(4).toString('hex').toUpperCase()}`;
    const nonce = crypto.randomBytes(8).toString('hex');
    const quotePayload = {
      quoteId,
      productId,
      priceEur: price,
      nonce,
      expiresAt: Date.now() + 600000 // 10 min
    };

    const signature = crypto.createHmac('sha256', this.secretKey)
      .update(JSON.stringify(quotePayload))
      .digest('hex');

    return {
      ...quotePayload,
      signature
    };
  }

  issueLicenseToken({ quote, agentId, paymentProof }) {
    if (!quote || !quote.quoteId || !quote.signature) {
      throw new Error('[M2M_ERROR] Invalid quote');
    }
    if (!paymentProof || paymentProof.verified !== true || paymentProof.amountEur !== quote.priceEur) {
      throw new Error('[M2M_ERROR] Invalid or unverified payment proof');
    }

    // Verify quote signature
    const { signature, ...payload } = quote;
    const expectedSig = crypto.createHmac('sha256', this.secretKey)
      .update(JSON.stringify(payload))
      .digest('hex');

    if (signature !== expectedSig) {
      throw new Error('[M2M_ERROR] Quote signature mismatch');
    }

    const licenseId = `LIC-${quote.productId}-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
    const licenseToken = crypto.createHmac('sha256', this.secretKey)
      .update(`${licenseId}:${quote.productId}:${agentId}:${quote.nonce}`)
      .digest('hex');

    const record = {
      licenseId,
      productId: quote.productId,
      agentId,
      priceEur: quote.priceEur,
      issuedAt: new Date().toISOString(),
      licenseToken
    };

    this.issuedLicenses.set(licenseId, record);
    return record;
  }

  verifyLicenseOffline(licenseRecord) {
    if (!licenseRecord || !licenseRecord.licenseId || !licenseRecord.licenseToken) {
      return false;
    }
    const stored = this.issuedLicenses.get(licenseRecord.licenseId);
    if (!stored) return false;

    return stored.licenseToken === licenseRecord.licenseToken;
  }
}

module.exports = { M2MCommerceValidator };
