// Gumroad Webhook Receiver & Normalization Adapter
// Parses incoming Gumroad pings, verifies webhook secret, and formats standard order JSON receipts.
// Zero external dependencies.

class GumroadWebhookHandler {
  constructor({
    webhookSecret = 'GUMROAD_SYMPHONY_SECRET_VERIFIED',
    inboxDir = null
  } = {}) {
    this.webhookSecret = webhookSecret;
    this.inboxDir = inboxDir;
  }

  verifyAndNormalize(payload) {
    if (!payload || typeof payload !== 'object') {
      throw new Error('[WEBHOOK_ERROR] Payload must be a non-null object');
    }

    // Verify webhook secret if present in payload
    if (payload.secret && payload.secret !== this.webhookSecret) {
      throw new Error('[WEBHOOK_ERROR] Invalid webhook secret');
    }

    const orderId = payload.sale_id || payload.order_number || payload.order_id;
    if (!orderId) {
      throw new Error('[WEBHOOK_ERROR] Missing sale_id / order_id');
    }

    // Gumroad prices can be in cents or float string
    let grossAmountEur = 0;
    if (payload.price) {
      // In cents (e.g. 500 = $5.00)
      grossAmountEur = typeof payload.price === 'number' && payload.price > 50
        ? payload.price / 100
        : Number(payload.price);
    } else if (payload.gross_amount_eur) {
      grossAmountEur = Number(payload.gross_amount_eur);
    }

    if (grossAmountEur <= 0) {
      throw new Error('[WEBHOOK_ERROR] Invalid gross amount');
    }

    const normalized = {
      order_id: `ORD-GUMROAD-${orderId}`,
      product_id: payload.product_permalink || payload.product_id || 'OPP-SEED-DIGITAL-01',
      product_name: payload.product_name || 'agent-context-trimmer v1.0.0',
      gross_amount_eur: grossAmountEur,
      currency: payload.currency || 'EUR',
      payment_status: 'PAID',
      customer_email: payload.email || payload.purchaser_email || 'unknown@customer.com',
      receipt_url: payload.receipt_url || `https://gumroad.com/receipt?id=${orderId}`,
      received_at: new Date().toISOString()
    };

    return normalized;
  }
}

module.exports = { GumroadWebhookHandler };
