function triageFeedback(rawFeedback = {}) {
  const email = rawFeedback.email || 'anonymous@developer.org';
  const category = (rawFeedback.category || 'GENERAL').toUpperCase();
  const message = rawFeedback.message || '';
  const environment = rawFeedback.environment || 'UNKNOWN';

  const validCategories = ['BUG', 'FEATURE_REQUEST', 'RULE_PARSER', 'INTEGRATION', 'GENERAL'];
  const resolvedCategory = validCategories.includes(category) ? category : 'GENERAL';

  // Compute urgency heuristic
  let urgency = 'NORMAL';
  const lowerMsg = message.toLowerCase();
  if (lowerMsg.includes('crash') || lowerMsg.includes('syntaxerror') || lowerMsg.includes('corrupt')) {
    urgency = 'CRITICAL';
  } else if (lowerMsg.includes('enterprise') || lowerMsg.includes('team license') || lowerMsg.includes('invoice')) {
    urgency = 'HIGH_COMMERCIAL_VALUE';
  }

  return {
    ticket_id: 'TCK-' + Date.now() + '-' + Math.floor(Math.random() * 1000),
    timestamp_utc: new Date().toISOString(),
    customer_email: email,
    category: resolvedCategory,
    urgency,
    environment,
    summary: message.slice(0, 100),
    full_message: message,
    triage_status: 'QUEUED_FOR_INSPECTION'
  };
}

module.exports = { triageFeedback };
