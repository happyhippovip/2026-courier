function generateDeliveryMessage(orderData = {}) {
  const customerEmail = orderData.customer_email || 'buyer@example.com';
  const orderId = orderData.order_id || 'ORD-20260911-EUR5';
  const productName = orderData.product_name || 'agent-context-trimmer v1.0.0';
  const licenseKey = orderData.license_key || 'ACT-PROD-2026-88F1-4A9B';
  const downloadUrl = orderData.download_url || 'https://gumroad.com/d/agent-context-trimmer';
  const sha256Checksum = orderData.sha256 || 'f54d4893798939a48698516d01d14878a1768c78c3a903c73cf4c7e6c467a8ec';

  const plainText = `Thank you for your purchase of ${productName}!

Order ID: ${orderId}
License Key: ${licenseKey}
Download URL: ${downloadUrl}
SHA-256 Checksum: ${sha256Checksum}

QUICK START INSTRUCTIONS:
1. Unzip the package:
   unzip agent-context-trimmer-1.0.0.zip
2. Run your first audit:
   node bin/trimmer.js audit --dir ./your-project
3. Optimize your context:
   node bin/trimmer.js fix --dir ./your-project --backup

Support: Refer to agent_context_trimmer_docs.html or reply to this email.
`;

  const html = `<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f6f8fa; padding: 24px; color: #24292f;">
  <div style="max-width: 600px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 8px; border: 1px solid #d0d7de;">
    <h2 style="color: #0969da; margin-top: 0;">Your ${productName} is Ready!</h2>
    <p>Hi there,</p>
    <p>Thank you for purchasing <strong>${productName}</strong>. Your license and access links are confirmed below.</p>
    
    <div style="background: #f6f8fa; border: 1px solid #d0d7de; padding: 16px; border-radius: 6px; margin: 20px 0;">
      <p style="margin: 4px 0;"><strong>Order ID:</strong> ${orderId}</p>
      <p style="margin: 4px 0;"><strong>License Key:</strong> <code style="background: #eaeef2; padding: 2px 6px; border-radius: 4px;">${licenseKey}</code></p>
      <p style="margin: 4px 0;"><strong>SHA-256 Hash:</strong> <small style="word-break: break-all;">${sha256Checksum}</small></p>
    </div>

    <p style="text-align: center; margin: 28px 0;">
      <a href="${downloadUrl}" style="background: #2ea043; color: #fff; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; display: inline-block;">Download agent-context-trimmer v1.0.0</a>
    </p>

    <h3>Quick Start:</h3>
    <pre style="background: #0d1117; color: #79c0ff; padding: 12px; border-radius: 6px; overflow-x: auto;">node bin/trimmer.js audit --dir ./your-project</pre>

    <p style="color: #57606a; font-size: 13px; margin-top: 32px; border-top: 1px solid #d0d7de; padding-top: 16px;">
      Symphony Project Autonomous Commercial Subsystem | Zero-Tax Commercial Handoff
    </p>
  </div>
</body>
</html>`;

  return {
    recipient: customerEmail,
    subject: `Your ${productName} License & Download Link (${orderId})`,
    plain_text: plainText,
    html: html
  };
}

module.exports = { generateDeliveryMessage };
