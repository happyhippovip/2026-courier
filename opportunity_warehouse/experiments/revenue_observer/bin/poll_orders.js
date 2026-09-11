#!/usr/bin/env node
// poll_orders.js — Automated Single-Command Revenue Ingestion Poller
// Zero external dependencies.

const { RevenueObserver } = require('../lib/revenue_observer');

const observer = new RevenueObserver();
console.log('[POLL_ORDERS] Checking money_factory/inbox/orders/ for incoming orders...');
const results = observer.processInbox();

if (results.length === 0) {
  console.log('[POLL_ORDERS] Inbox empty. Zero pending orders.');
} else {
  console.log(`[POLL_ORDERS] Processed ${results.length} order(s):`);
  for (const r of results) {
    if (r.status === 'SETTLED') {
      console.log(`  ✓ SETTLED: Order ${r.order_id} (+€${r.revenue_eur.toFixed(2)}) -> Evidence: ${r.evidence_id}`);
    } else {
      console.log(`  ✗ REJECTED: File ${r.file} -> ${r.error}`);
    }
  }
}
