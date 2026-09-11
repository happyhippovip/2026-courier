function renderInvoiceHtml(orderData = {}) {
  const orderId = orderData.order_id || 'ORD-20260911-001';
  const customerEmail = orderData.customer_email || 'customer@example.com';
  const productName = orderData.product_name || 'agent-context-trimmer v1.0.0';
  const amountEur = orderData.amount_eur || 5.00;
  const paymentProvider = orderData.payment_provider || 'Gumroad';
  const settledAt = orderData.settled_at || new Date().toISOString();
  const licenseKeyHash = orderData.license_key_hash || 'ACT-8F92-4C10-E7A9';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Commercial Invoice - ${orderId}</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #24292f;
      background: #f6f8fa;
      padding: 40px;
      margin: 0;
    }
    .invoice-card {
      max-width: 650px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid #d0d7de;
      border-radius: 8px;
      padding: 32px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #0969da;
      padding-bottom: 16px;
      margin-bottom: 24px;
    }
    .header h1 { margin: 0; font-size: 20px; color: #0969da; }
    .status-badge {
      background: #dafbe1;
      color: #1a7f37;
      padding: 4px 12px;
      border-radius: 16px;
      font-weight: 600;
      font-size: 13px;
    }
    .meta-table {
      width: 100%;
      margin-bottom: 24px;
      border-collapse: collapse;
    }
    .meta-table td { padding: 6px 0; font-size: 14px; }
    .meta-table .label { color: #57606a; width: 140px; }
    .items-table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 24px;
    }
    .items-table th {
      background: #f6f8fa;
      border-bottom: 1px solid #d0d7de;
      padding: 10px;
      text-align: left;
      font-size: 13px;
    }
    .items-table td {
      border-bottom: 1px solid #d0d7de;
      padding: 12px 10px;
      font-size: 14px;
    }
    .total-row td {
      font-weight: bold;
      font-size: 16px;
      border-top: 2px solid #24292f;
    }
    .footer {
      font-size: 12px;
      color: #6e7781;
      text-align: center;
      margin-top: 32px;
      border-top: 1px solid #d0d7de;
      padding-top: 16px;
    }
  </style>
</head>
<body>
  <div class="invoice-card">
    <div class="header">
      <h1>COMMERCIAL RECEIPT & INVOICE</h1>
      <span class="status-badge">PAID & SETTLED</span>
    </div>

    <table class="meta-table">
      <tr><td class="label">Invoice / Order ID:</td><td><strong>${orderId}</strong></td></tr>
      <tr><td class="label">Date Settled:</td><td>${settledAt}</td></tr>
      <tr><td class="label">Billed To:</td><td>${customerEmail}</td></tr>
      <tr><td class="label">Payment Provider:</td><td>${paymentProvider}</td></tr>
      <tr><td class="label">License Key Fingerprint:</td><td><code>${licenseKeyHash}</code></td></tr>
    </table>

    <table class="items-table">
      <thead>
        <tr>
          <th>Item Description</th>
          <th style="text-align: center;">Qty</th>
          <th style="text-align: right;">Price</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>${productName} (Single-Developer Commercial License)</td>
          <td style="text-align: center;">1</td>
          <td style="text-align: right;">€${amountEur.toFixed(2)}</td>
        </tr>
        <tr class="total-row">
          <td colspan="2">Total Paid:</td>
          <td style="text-align: right;">€${amountEur.toFixed(2)} EUR</td>
        </tr>
      </tbody>
    </table>

    <div class="footer">
      Symphony Project Autonomous Commercial Subsystem | Zero-Tax Commercial Handoff<br>
      For developer support, refer to <code>agent_context_trimmer_docs.html</code>.
    </div>
  </div>
</body>
</html>`;
}

module.exports = { renderInvoiceHtml };
