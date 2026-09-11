const assert = require('assert');
const { SocialCardGenerator } = require('../lib/social_card_generator');

console.log('Testing SocialCardGenerator...');

const generator = new SocialCardGenerator();

// Test 1: Generate valid SVG
const svg = generator.generateSocialCardSvg();
assert.ok(svg.startsWith('<svg'));
assert.ok(svg.endsWith('</svg>'));
assert.ok(svg.includes('viewBox="0 0 1200 630"'));

// Test 2: Injected stats
assert.ok(svg.includes('-41.2% Input Tokens'));
assert.ok(svg.includes('5.3-Day ROI Payback'));

// Test 3: Custom branding
const customSvg = generator.generateSocialCardSvg({
  title: 'Custom Title',
  stat1: '-50% Tokens'
});
assert.ok(customSvg.includes('Custom Title'));
assert.ok(customSvg.includes('-50% Tokens'));

console.log('All SocialCardGenerator tests passed (3/3)!');
