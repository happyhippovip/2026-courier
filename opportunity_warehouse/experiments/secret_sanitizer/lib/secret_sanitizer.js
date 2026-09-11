// High-speed zero-dependency secret scanner and sanitizer
const SECRET_PATTERNS = [
  { type: 'OPENAI_API_KEY', regex: /sk-[a-zA-Z0-9]{32,64}/g },
  { type: 'ANTHROPIC_API_KEY', regex: /sk-ant-[a-zA-Z0-9_\-]{32,64}/g },
  { type: 'GOOGLE_API_KEY', regex: /AIza[0-9A-Za-z_\-]{35}/g },
  { type: 'AWS_ACCESS_KEY', regex: /AKIA[0-9A-Z]{16}/g },
  { type: 'DATABASE_URL', regex: /(postgres|postgresql|mongodb|mysql):\/\/[^\s'"]+:[^\s'"]+@[^\s'"]+/g },
  { type: 'GENERIC_BEARER', regex: /Bearer\s+[a-zA-Z0-9_\-\.]{24,}/gi }
];

function scanAndSanitize(content) {
  let sanitized = content;
  const detectedSecrets = [];

  for (const pat of SECRET_PATTERNS) {
    let match;
    // Reset regex index
    pat.regex.lastIndex = 0;
    while ((match = pat.regex.exec(content)) !== null) {
      const secretVal = match[0];
      detectedSecrets.push({
        type: pat.type,
        redacted_preview: secretVal.slice(0, 4) + '...' + secretVal.slice(-4),
        index: match.index
      });
    }
    sanitized = sanitized.replace(pat.regex, `{{REDACTED_SECRET_${pat.type}}}`);
  }

  return {
    is_clean: detectedSecrets.length === 0,
    secrets_count: detectedSecrets.length,
    detected_secrets: detectedSecrets,
    sanitized_content: sanitized,
    scanned_at: new Date().toISOString()
  };
}

module.exports = { scanAndSanitize, SECRET_PATTERNS };
