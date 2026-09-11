// Mock Order Injector & Concurrency Test Generator
// Generates realistic test order payloads for settlement testing.
// Zero external dependencies.

const crypto = require('crypto');

class MockOrderGenerator {
  static generateOrder({
    productId = 'OPP-SEED-DIGITAL-01',
    productName = 'agent-context-trimmer v1.0.0',
    grossAmountEur = 5.00,
    currency = 'EUR',
    countryCode = 'DE',
    customerEmail = null
  } = {}) {
    const saleId = crypto.randomBytes(4).toString('hex').toUpperCase();
    const email = customerEmail || `dev_${saleId.toLowerCase()}@engineer.io`;
    const orderId = `ORD-TEST-${saleId}`;

    return {
      order_id: orderId,
      product_id: productId,
      product_name: productName,
      gross_amount_eur: grossAmountEur,
      currency: currency,
      payment_status: 'PAID',
      customer_email: email,
      country_code: countryCode,
      receipt_url: `https://gumroad.com/receipt?id=${orderId}`,
      created_at: new Date().toISOString()
    };
  }

  static generateBatch(count = 5) {
    const batch = [];
    for (let i = 0; i < count; i++) {
      batch.push(this.generateOrder());
    }
    return batch;
  }
}

module.exports = { MockOrderGenerator };
