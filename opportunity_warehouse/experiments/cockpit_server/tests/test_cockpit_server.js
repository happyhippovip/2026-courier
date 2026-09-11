const assert = require('assert');
const http = require('http');
const { CockpitServer } = require('../lib/cockpit_server');

console.log('--- TEST 1: Status Payload Generation ---');
const server = new CockpitServer({ port: 4429 });
const status = server.createStatusPayload();

assert.strictEqual(status.status, 'OPERATIONAL');
assert.strictEqual(typeof status.symphony_overall_percent, 'number');
assert.strictEqual(status.active_leases, 0);
assert.strictEqual(status.spend_limit_eur, 0.0);
console.log('PASS [Test 1]: Invariant status payload compiled cleanly.');

console.log('--- TEST 2: HTTP Server Start & API Query ---');
server.start().then(() => {
  http.get('http://localhost:4429/api/status', (res) => {
    assert.strictEqual(res.statusCode, 200);
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      const parsed = JSON.parse(data);
      assert.strictEqual(parsed.status, 'OPERATIONAL');
      server.stop().then(() => {
        console.log('PASS [Test 2]: Server responded to /api/status with 200 OK.');
        console.log('\n>>> ALL 2 COCKPIT SERVER TESTS PASS (100% DETERMINISTIC) <<<');
      });
    });
  });
});
