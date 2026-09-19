// Local stub program for adapter tests only. Never a real Muse proof.
// Modes driven by argv: --mode=ok|partial|fail|slow|ignore-term --marker=TEXT --bytes=N --sleep=MS
const args = Object.fromEntries(process.argv.slice(2).map(a => {
  const m = /^--([^=]+)=(.*)$/.exec(a); return m ? [m[1], m[2]] : [a, 'true'];
}));
const mode = args.mode || 'ok';
const marker = args.marker || 'COURIER_DONE';
const sleepMs = Number(args.sleep || '0');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const flushWrite = s => new Promise(res => { if (process.stdout.write(s)) res(); else process.stdout.once('drain', res); });
let ignoreTerm = false;
process.on('SIGTERM', () => { if (!ignoreTerm) process.exit(143); });
await sleep(sleepMs);
if (mode === 'ignore-term') ignoreTerm = true;
if (mode === 'fail') { console.log('stub failing'); process.exit(3); }
if (mode === 'auth') { process.stderr.write('AUTH_REQUIRED\n'); process.exit(4); }
if (mode === 'payment') { process.stderr.write('PAYMENT_REQUIRED\n'); process.exit(5); }
const errBig = 'e'.repeat(Number(args.errbytes || '0'));
if (errBig) await new Promise(res => { if (process.stderr.write(errBig)) res(); else process.stderr.once('drain', res); });
const big = 'x'.repeat(Number(args.bytes || '0'));
if (big) await flushWrite(big); // drain before exit, else the pipe truncates
if (mode === 'partial') { process.stdout.write('half-output-no-marker'); process.exit(0); }
if (mode === 'slow') { await flushWrite('partial-before-timeout'); await sleep(Number(args.extra || '5000')); }
console.log(marker);
process.exit(0);
