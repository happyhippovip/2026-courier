function simulateWebhookDelivery(endpointUrl, payload, options = {}) {
  const maxRetries = options.maxRetries || 3;
  const mockStatus = options.mockStatus !== undefined ? options.mockStatus : 200;
  const attempts = [];

  let isDelivered = false;
  let attemptCount = 0;

  while (attemptCount < maxRetries && !isDelivered) {
    attemptCount++;
    const isSuccess = mockStatus >= 200 && mockStatus < 300;
    const backoffMs = attemptCount === 1 ? 0 : Math.pow(2, attemptCount - 1) * 1000;

    attempts.push({
      attempt_number: attemptCount,
      backoff_delay_ms: backoffMs,
      http_status: isSuccess ? mockStatus : (attemptCount < maxRetries ? 503 : mockStatus),
      success: isSuccess,
      timestamp: new Date(Date.now() + backoffMs).toISOString()
    });

    if (isSuccess) {
      isDelivered = true;
    }
  }

  return {
    endpoint: endpointUrl,
    total_attempts: attemptCount,
    delivered: isDelivered,
    dead_letter: !isDelivered,
    attempts,
    monitored_at: new Date().toISOString()
  };
}

module.exports = { simulateWebhookDelivery };
