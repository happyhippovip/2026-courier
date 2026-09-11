const assert = require('assert');
const { buildDiscordOrderNotification, buildSlackOrderNotification } = require('../lib/webhook_dispatcher');

console.log('Running Community Webhook Dispatcher Tests...');

// Test 1: Discord payload formatting
const discord = buildDiscordOrderNotification({ order_id: 'GUM-TEST-100', amount_eur: 5.00 });
assert.strictEqual(discord.username, 'Symphony Commercial Observer');
assert.strictEqual(discord.embeds[0].color, 0x2ea043);
assert.ok(discord.embeds[0].fields[0].value.includes('GUM-TEST-100'));
console.log('  [PASS] Test 1: Discord embed payload verified');

// Test 2: Slack Block Kit payload formatting
const slack = buildSlackOrderNotification({ order_id: 'GUM-TEST-100', amount_eur: 5.00 });
assert.strictEqual(slack.blocks[0].type, 'header');
assert.strictEqual(slack.blocks[1].type, 'section');
assert.ok(slack.blocks[1].fields[1].text.includes('€5.00 EUR'));
console.log('  [PASS] Test 2: Slack Block Kit payload verified');

// Test 3: Timestamp validity
assert.ok(new Date(discord.embeds[0].timestamp).getTime() > 0);
console.log('  [PASS] Test 3: ISO timestamp formatting confirmed');

console.log('ALL 3 WEBHOOK DISPATCHER TESTS PASSED DETERMINISTICALLY!');
