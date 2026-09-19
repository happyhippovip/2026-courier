// Optional resume trigger, not a queue, worker, or scheduling authority.
export const INTERVAL_MS = 120_000;
export const REQUEST_TIMEOUT_MS = 10_000;
export const CONTRACT = 'courier-existing-session-resume/v1';

export class WorkScript {
  constructor({adapter = null, storage, lock, now = Date.now,
    setTimer = setTimeout, clearTimer = clearTimeout, onChange = () => {}, prompt}) {
    Object.assign(this, {adapter, storage, lock, now, setTimer, clearTimer, onChange, prompt});
    this.enabled = false;
    this.epoch = 0;
    this.timer = null;
    this.inflight = false;
    this.state = {status: 'OFF', enabled: false, nextCheckAt: null, lastReceipt: null};
  }

  emit(status, extra = {}) {
    this.state = {...this.state, status, enabled: this.enabled, ...extra};
    this.onChange({...this.state});
  }

  stop(status = 'OFF') {
    this.enabled = false;
    this.epoch++;
    if (this.timer !== null) this.clearTimer(this.timer);
    this.timer = null;
    this.abort?.abort();
    this.emit(status, {nextCheckAt: null});
    // Already accepted external work is never killed by this toggle.
  }

  start() {
    if (this.enabled) return;
    if (!this.adapter || this.adapter.contract !== CONTRACT) {
      this.emit('NOT_CONNECTED'); return;
    }
    if (!this.storage || !this.lock || !this.prompt?.trim()) {
      this.emit('BLOCKED_CONFIGURATION'); return;
    }
    this.enabled = true;
    this.epoch++;
    this.emit('ARMED');
    this.schedule(); // First check after 120 seconds, never an immediate spam send.
  }

  schedule() {
    if (!this.enabled) return;
    if (this.timer !== null) this.clearTimer(this.timer);
    const epoch = this.epoch;
    this.emit(this.state.status, {nextCheckAt: this.now() + INTERVAL_MS});
    this.timer = this.setTimer(() => {
      if (!this.enabled || epoch !== this.epoch) return;
      this.timer = null;
      void this.tick();
    }, INTERVAL_MS);
  }

  async bounded(operation) {
    const abort = new AbortController();
    this.abort = abort;
    let timer;
    try {
      return await Promise.race([
        Promise.resolve().then(() => operation(abort.signal)),
        new Promise((_, reject) => {
          timer = this.setTimer(() => {abort.abort(); reject(new Error('timeout'));}, REQUEST_TIMEOUT_MS);
        })
      ]);
    } finally {
      this.clearTimer(timer);
      if (this.abort === abort) this.abort = null;
    }
  }

  readJournal() {
    const raw = this.storage.getItem('courier.work-script.v1');
    if (raw === null) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object' ||
        Object.values(parsed).some(x => !['PENDING', 'ACCEPTED', 'REJECTED'].includes(x))) {
      throw new Error('invalid journal');
    }
    return parsed;
  }

  async tick() {
    if (!this.enabled || this.inflight) return;
    if (this.timer !== null) this.clearTimer(this.timer);
    this.timer = null;
    this.inflight = true;
    const epoch = this.epoch;
    const current = () => this.enabled && this.epoch === epoch;
    try {
      await this.lock(async acquired => {
        if (!current()) return;
        if (!acquired) {this.emit('BUSY_OTHER_TAB'); return;}
        const journal = this.readJournal();
        if (Object.values(journal).includes('PENDING')) {
          this.stop('BLOCKED_UNCONFIRMED'); return;
        }
        const snapshot = await this.bounded(signal => this.adapter.inspect({signal}));
        if (!current()) return;
        // The adapter is provided by the owner. These checks do not authenticate it.
        if (!snapshot || snapshot.contract !== CONTRACT) {this.stop('BLOCKED_PROTOCOL'); return;}
        if (snapshot.status === 'BUSY') {this.emit('BUSY'); return;}
        if (snapshot.status === 'IDLE') {this.stop('IDLE'); return;}
        const g = snapshot.grant;
        const required = ['operation_id', 'goal_id', 'task_id', 'attempt_id', 'fingerprint',
          'session_id', 'runtime_id', 'lease_token'];
        if (snapshot.status !== 'READY' || !g ||
            required.some(k => typeof g[k] !== 'string' || !g[k].trim()) ||
            !Number.isFinite(g.expires_at) || g.expires_at <= this.now() ||
            g.session_idle !== true || g.scope_owned !== true || g.allowed !== true ||
            g.cost_authorized !== true || g.human_gate !== false) {
          this.stop('BLOCKED_AUTHORITY'); return;
        }
        // Stable operation identity is issued by the canonical owner; never timestamp it here.
        const key = JSON.stringify([g.goal_id, g.task_id, g.attempt_id, g.fingerprint]);
        if (Object.hasOwn(journal, key)) {this.emit('UNCHANGED'); return;}
        if (Object.keys(journal).length >= 1000) {this.stop('BLOCKED_JOURNAL_FULL'); return;}
        journal[key] = 'PENDING';
        this.storage.setItem('courier.work-script.v1', JSON.stringify(journal));
        if (!current()) return;
        this.emit('SUBMITTING');
        const receipt = await this.bounded(signal => this.adapter.submit({
          grant: g, prompt: this.prompt, idempotency_key: g.operation_id, signal
        }));
        // Persist authoritative ACK even if operator clicked OFF while request was in flight.
        if (!receipt || receipt.operation_id !== g.operation_id ||
            receipt.session_id !== g.session_id || receipt.task_id !== g.task_id ||
            !['ACCEPTED', 'REJECTED'].includes(receipt.status)) {
          if (current()) this.stop('BLOCKED_UNCONFIRMED');
          return;
        }
        journal[key] = receipt.status;
        this.storage.setItem('courier.work-script.v1', JSON.stringify(journal));
        if (current()) {
          if (receipt.status === 'REJECTED') this.stop('BLOCKED_REJECTED');
          else this.emit('SENT', {lastReceipt: this.now()});
        }
      });
    } catch {
      // Uncertain delivery is never automatically retried; no credential/error-body logging.
      if (current()) this.stop('BLOCKED_CHECK_OR_DELIVERY');
    } finally {
      this.inflight = false;
      if (current()) this.schedule();
    }
  }
}
