// Append-Only Framed Durable Event Log with SHA-256 Checksums
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { SchemaRegistry } = require('./SchemaRegistry');

class DurableEventLog {
  constructor(filePath) {
    this.filePath = filePath;
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    if (!fs.existsSync(this.filePath)) fs.writeFileSync(this.filePath, '', 'utf8');
  }

  append(entry) {
    const val = SchemaRegistry.validateEvent(entry);
    if (!val.valid) throw new Error('Schema validation failed: ' + val.error);

    const payload = JSON.stringify(val.event);
    const len = Buffer.byteLength(payload, 'utf8');
    const cs = crypto.createHash('sha256').update(payload).digest('hex').substring(0, 16);
    const frame = `FRAME:${len}:${cs}\n${payload}\n`;
    fs.appendFileSync(this.filePath, frame, 'utf8');
    return { checksum: cs, length: len, event: val.event };
  }

  recoverAndReplay() {
    if (!fs.existsSync(this.filePath)) return { validEntries: [], tornEntries: 0 };
    const content = fs.readFileSync(this.filePath, 'utf8');
    const lines = content.split('\n');
    const validEntries = [];
    let tornEntries = 0;

    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      if (line.startsWith('FRAME:')) {
        const parts = line.split(':');
        const expLen = parseInt(parts[1], 10);
        const expCs = parts[2];
        const payloadLine = lines[i + 1];
        if (payloadLine === undefined) {
          tornEntries++;
          break;
        }
        const actLen = Buffer.byteLength(payloadLine, 'utf8');
        const actCs = crypto.createHash('sha256').update(payloadLine).digest('hex').substring(0, 16);
        if (actLen === expLen && actCs === expCs) {
          try {
            validEntries.push(JSON.parse(payloadLine));
          } catch (e) {
            tornEntries++;
          }
          i += 2;
        } else {
          tornEntries++;
          i += 2;
        }
      } else {
        tornEntries++;
        i++;
      }
    }
    return { validEntries, tornEntries };
  }

  size() {
    if (!fs.existsSync(this.filePath)) return 0;
    return fs.statSync(this.filePath).size;
  }
}

module.exports = { DurableEventLog };
