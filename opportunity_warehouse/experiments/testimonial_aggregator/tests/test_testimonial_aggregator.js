const assert = require('assert');
const { renderTestimonialsHtml, generateJsonLdSchema } = require('../lib/testimonial_engine');

console.log('Running Testimonial Aggregator Tests...');

const sampleData = [
  { author: 'Marcus V.', role: 'Senior AI Engineer', quote: 'Saved 44% tokens on our .cursorrules in seconds.', verified_metric: '-44% Tokens Pruned' },
  { author: 'Elena R.', role: 'Staff Backend Lead', quote: 'Pays for itself on day 3. Zero regressions.', verified_metric: '-280ms Latency' }
];

// Test 1: HTML generation
const html = renderTestimonialsHtml(sampleData);
assert.ok(html.includes('Marcus V.'));
assert.ok(html.includes('Elena R.'));
assert.ok(html.includes('testimonial-card'));
console.log('  [PASS] Test 1: Testimonials HTML rendering verified');

// Test 2: Metrics pill rendering
assert.ok(html.includes('-44% Tokens Pruned'));
assert.ok(html.includes('-280ms Latency'));
console.log('  [PASS] Test 2: Verified metrics pills rendered');

// Test 3: JSON-LD SEO Schema
const schema = generateJsonLdSchema(sampleData);
assert.strictEqual(schema['@type'], 'Product');
assert.strictEqual(schema.aggregateRating.reviewCount, '2');
assert.strictEqual(schema.review.length, 2);
console.log('  [PASS] Test 3: Structured JSON-LD SEO schema verified');

console.log('ALL 3 TESTIMONIAL AGGREGATOR TESTS PASSED DETERMINISTICALLY!');
