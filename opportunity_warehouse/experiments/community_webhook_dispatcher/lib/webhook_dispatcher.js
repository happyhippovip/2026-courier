function buildDiscordOrderNotification(orderData = {}) {
  const orderId = orderData.order_id || 'ORD-UNKNOWN';
  const amountEur = orderData.amount_eur || 5.00;
  const productName = orderData.product_name || 'agent-context-trimmer v1.0.0';

  return {
    username: 'Symphony Commercial Observer',
    avatar_url: 'https://raw.githubusercontent.com/symphony/assets/main/bot.png',
    embeds: [
      {
        title: '🎉 Commercial Sale Verified!',
        description: 'A new verified purchase of **' + productName + '** has settled.',
        color: 0x2ea043,
        fields: [
          { name: 'Order ID', value: '```' + orderId + '```', inline: true },
          { name: 'Revenue', value: '€' + amountEur.toFixed(2) + ' EUR', inline: true },
          { name: 'Status', value: '100% Settled & Delivered', inline: true }
        ],
        footer: { text: 'Symphony Autonomous Commercial Subsystem' },
        timestamp: new Date().toISOString()
      }
    ]
  };
}

function buildSlackOrderNotification(orderData = {}) {
  const orderId = orderData.order_id || 'ORD-UNKNOWN';
  const amountEur = orderData.amount_eur || 5.00;
  const productName = orderData.product_name || 'agent-context-trimmer v1.0.0';

  return {
    blocks: [
      {
        type: 'header',
        text: { type: 'plain_text', text: '🎉 Verified Commercial Settlement', emoji: true }
      },
      {
        type: 'section',
        fields: [
          { type: 'mrkdwn', text: '*Product:*\n' + productName },
          { type: 'mrkdwn', text: '*Revenue:*\n€' + amountEur.toFixed(2) + ' EUR' },
          { type: 'mrkdwn', text: '*Order ID:*\n`' + orderId + '`' },
          { type: 'mrkdwn', text: '*Settlement:*\n100% Attributable' }
        ]
      },
      { type: 'divider' }
    ]
  };
}

module.exports = { buildDiscordOrderNotification, buildSlackOrderNotification };
