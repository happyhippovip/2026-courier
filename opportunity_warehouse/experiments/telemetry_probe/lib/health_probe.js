const fs = require('fs');
const path = require('path');
const os = require('os');

function inspectSystemHealth(options = {}) {
  const rootDir = options.rootDir || process.cwd();
  const checks = {};
  let isDegraded = false;

  // 1. Node & Host runtime metrics
  const memUsage = process.memoryUsage();
  checks.runtime = {
    node_version: process.version,
    platform: process.platform,
    arch: process.arch,
    pid: process.pid,
    uptime_sec: Math.floor(process.uptime()),
    heap_used_mb: Math.round((memUsage.heapUsed / 1024 / 1024) * 100) / 100,
    heap_total_mb: Math.round((memUsage.heapTotal / 1024 / 1024) * 100) / 100,
    os_free_mem_mb: Math.round((os.freemem() / 1024 / 1024) * 100) / 100,
    status: 'OK'
  };

  // 2. Directory Access Checks
  const dirsToCheck = [
    { name: 'inbox_orders', relPath: 'money_factory/inbox/orders' },
    { name: 'opportunity_warehouse', relPath: 'opportunity_warehouse' },
    { name: 'evidence', relPath: 'opportunity_warehouse/evidence' }
  ];

  checks.directories = {};
  for (const dir of dirsToCheck) {
    const full = path.join(rootDir, dir.relPath);
    if (fs.existsSync(full)) {
      try {
        fs.accessSync(full, fs.constants.R_OK | fs.constants.W_OK);
        checks.directories[dir.name] = { accessible: true, writable: true, status: 'OK' };
      } catch {
        checks.directories[dir.name] = { accessible: true, writable: false, status: 'READ_ONLY' };
      }
    } else {
      checks.directories[dir.name] = { accessible: false, writable: false, status: 'MISSING' };
      isDegraded = true;
    }
  }

  // 3. Active Leases Check
  const leaseFile = path.join(rootDir, 'runtime/leases/leases.json');
  checks.leases = { active_leases_count: 0, status: 'OK' };
  if (fs.existsSync(leaseFile)) {
    try {
      const leaseData = JSON.parse(fs.readFileSync(leaseFile, 'utf8'));
      const active = Array.isArray(leaseData) ? leaseData.length : Object.keys(leaseData.active_leases || {}).length;
      checks.leases.active_leases_count = active;
    } catch {
      checks.leases.status = 'PARSE_ERROR';
    }
  }

  // 4. Order Queue Status
  const ordersDir = path.join(rootDir, 'money_factory/inbox/orders');
  checks.orders = { pending_count: 0, status: 'OK' };
  if (fs.existsSync(ordersDir)) {
    try {
      const items = fs.readdirSync(ordersDir).filter(f => f.endsWith('.json'));
      checks.orders.pending_count = items.length;
    } catch {
      checks.orders.status = 'SCAN_ERROR';
    }
  }

  return {
    probe_id: 'PROBE-' + Date.now(),
    timestamp_utc: new Date().toISOString(),
    overall_status: isDegraded ? 'DEGRADED' : 'HEALTHY',
    checks
  };
}

module.exports = { inspectSystemHealth };
