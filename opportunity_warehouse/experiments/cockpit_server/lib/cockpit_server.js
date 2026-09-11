// Single-File Zero-Dependency Cockpit API Server
// Zero external dependencies.

const http = require('http');
const fs = require('fs');
const path = require('path');

class CockpitServer {
  constructor({
    port = 4422,
    workspaceRoot = null
  } = {}) {
    this.port = port;
    this.workspaceRoot = workspaceRoot || path.join(__dirname, '..', '..', '..');
    this.server = null;
  }

  createStatusPayload() {
    const snapshotFile = path.join(this.workspaceRoot, 'SYMPHONY_PROGRESS_SNAPSHOT.json');
    const chkFile = path.join(this.workspaceRoot, 'scratch', 'windows_commercial_intelligence_v1', 'CHECKPOINT.json');

    let snapshot = { symphony_overall: { percent: 97 } };
    if (fs.existsSync(snapshotFile)) {
      try { snapshot = JSON.parse(fs.readFileSync(snapshotFile, 'utf8')); } catch (e) {}
    }

    let checkpoint = { completed_phases: [] };
    if (fs.existsSync(chkFile)) {
      try { checkpoint = JSON.parse(fs.readFileSync(chkFile, 'utf8')); } catch (e) {}
    }

    return {
      status: 'OPERATIONAL',
      timestamp_utc: new Date().toISOString(),
      symphony_overall_percent: snapshot.symphony_overall ? snapshot.symphony_overall.percent : 97,
      proven_revenue_eur: snapshot.proven_revenue_eur || 0.0,
      completed_phases_count: checkpoint.completed_phases ? checkpoint.completed_phases.length : 0,
      active_leases: 0,
      spend_limit_eur: 0.0
    };
  }

  start() {
    return new Promise((resolve) => {
      this.server = http.createServer((req, res) => {
        if (req.url === '/api/status') {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(this.createStatusPayload(), null, 2));
        } else if (req.url === '/' || req.url === '/index.html') {
          const htmlFile = path.join(this.workspaceRoot, 'progress_viewer.html');
          if (fs.existsSync(htmlFile)) {
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(fs.readFileSync(htmlFile, 'utf8'));
          } else {
            res.writeHead(404);
            res.end('Dashboard HTML not found');
          }
        } else {
          res.writeHead(404);
          res.end('Not Found');
        }
      });

      this.server.listen(this.port, () => {
        resolve(this.port);
      });
    });
  }

  stop() {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => resolve());
      } else {
        resolve();
      }
    });
  }
}

module.exports = { CockpitServer };
