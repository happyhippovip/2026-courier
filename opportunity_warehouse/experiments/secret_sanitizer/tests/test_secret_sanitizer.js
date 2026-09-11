const assert = require('assert');
const { scanAndSanitize } = require('../lib/secret_sanitizer');

console.log('Running Secret Sanitizer Tests...');

// Test 1: Clean text returns is_clean = true
const cleanRes = scanAndSanitize('This is a prompt with no secrets.');
assert.strictEqual(cleanRes.is_clean, true);
assert.strictEqual(cleanRes.secrets_count, 0);
console.log('  [PASS] Test 1: Clean text verified');

// Test 2: OpenAI and Anthropic API key detection & redaction
const leakText = 'My OpenAI key is sk-12345678901234567890123456789012 and Anthropic is sk-ant-api03-abcdefghijklmnopqrstuvwxyz123456.';
const leakRes = scanAndSanitize(leakText);
assert.strictEqual(leakRes.is_clean, false);
assert.strictEqual(leakRes.secrets_count, 2);
assert.ok(leakRes.sanitized_content.includes('{{REDACTED_SECRET_OPENAI_API_KEY}}'));
assert.ok(leakRes.sanitized_content.includes('{{REDACTED_SECRET_ANTHROPIC_API_KEY}}'));
console.log('  [PASS] Test 2: AI provider secret keys detected and redacted');

// Test 3: Database URL detection
const dbText = 'Connect using postgres://user:super_secret_password@db.supabase.co:5432/mydb';
const dbRes = scanAndSanitize(dbText);
assert.strictEqual(dbRes.secrets_count, 1);
assert.ok(dbRes.sanitized_content.includes('{{REDACTED_SECRET_DATABASE_URL}}'));
console.log('  [PASS] Test 3: Database credentials intercepted and redacted');

// Test 4: AWS Key detection
const awsText = 'Deploy with AKIAIOSFODNN7EXAMPLE';
const awsRes = scanAndSanitize(awsText);
assert.strictEqual(awsRes.secrets_count, 1);
assert.ok(awsRes.sanitized_content.includes('{{REDACTED_SECRET_AWS_ACCESS_KEY}}'));
console.log('  [PASS] Test 4: AWS credentials redacted');

console.log('ALL 4 SECRET SANITIZER TESTS PASSED DETERMINISTICALLY!');
