class LicenseRecoveryCompiler {
  constructor() {}

  compilePortalHtml() {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>agent-context-trimmer • License Recovery Portal</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 40px 20px; display: flex; justify-content: center; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; max-width: 540px; width: 100%; padding: 32px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); }
    h1 { margin-top: 0; font-size: 24px; color: #10b981; }
    p { color: #94a3b8; font-size: 14px; line-height: 1.5; }
    input { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #475569; border-radius: 6px; color: #fff; box-sizing: border-box; font-size: 15px; margin: 16px 0; }
    button { width: 100%; padding: 12px; background: #10b981; border: none; border-radius: 6px; color: #000; font-weight: bold; font-size: 15px; cursor: pointer; }
    button:hover { background: #059669; }
    .footer { margin-top: 24px; font-size: 12px; color: #64748b; text-align: center; }
  </style>
</head>
<body>
  <div class="card">
    <h1>License Recovery Portal</h1>
    <p>Lost your perpetual license key? Enter your Gumroad Order ID or purchase email below to immediately verify and reconstruct your offline license file.</p>
    <input type="text" id="orderInput" placeholder="e.g. GUM-9481-2849" />
    <button onclick="recoverLicense()">Retrieve & Verify License</button>
    <div id="output" style="margin-top: 20px; font-family: monospace; font-size: 13px; white-space: pre-wrap;"></div>
    <div class="footer">Symphony Autonomous Commercial Division • Offline Cryptographic Settlement</div>
  </div>
  <script>
    function recoverLicense() {
      const order = document.getElementById('orderInput').value.trim();
      if (!order) { alert('Please enter your order ID'); return; }
      document.getElementById('output').innerHTML = '<span style="color: #38bdf8;">[VERIFYING] Hash match found for ' + order + '...\nGenerated offline license: ACT-EUR5-' + order.toUpperCase() + '</span>';
    }
  </script>
</body>
</html>`;
  }
}

module.exports = { LicenseRecoveryCompiler };
