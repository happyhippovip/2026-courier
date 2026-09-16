'use strict';

/**
 * ChaosEngine
 * Deterministic, seed-driven fault injection engine.
 * Simulates real-world hardware, network, and OS faults with exact reproducibility.
 */
class ChaosEngine {
  constructor(seed = 1337) {
    this.seed = seed;
    this.rng = this._mulberry32(seed);
    this.injectionLog = [];
    this.virtualClockOffsetMs = 0;
  }

  _mulberry32(a) {
    return function() {
      let t = (a += 0x6d2b79f5);
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  random() {
    return this.rng();
  }

  randomInt(min, max) {
    return Math.floor(this.random() * (max - min + 1)) + min;
  }

  injectFault(faultType, context = {}) {
    const event = {
      fault_type: faultType,
      seed: this.seed,
      timestamp_ms: Date.now() + this.virtualClockOffsetMs,
      context
    };
    this.injectionLog.push(event);

    switch (faultType) {
      case 'DISK_FULL': {
        const err = new Error('ENOSPC: no space left on device, write');
        err.code = 'ENOSPC';
        throw err;
      }
      case 'PERMISSION_DENIED': {
        const err = new Error('EACCES: permission denied, open');
        err.code = 'EACCES';
        throw err;
      }
      case 'PROCESS_SIGNAL': {
        const signal = context.signal || 'SIGKILL';
        return { action: 'PROCESS_TERMINATED', signal, exit_code: signal === 'SIGKILL' ? 137 : 143 };
      }
      case 'CLOCK_JUMP_FORWARD': {
        const deltaMs = context.deltaMs || 3600000; // 1 hour default
        this.virtualClockOffsetMs += deltaMs;
        return { action: 'CLOCK_ADVANCED', new_offset_ms: this.virtualClockOffsetMs };
      }
      case 'CLOCK_JUMP_BACKWARD': {
        const deltaMs = context.deltaMs || 3600000;
        this.virtualClockOffsetMs -= deltaMs;
        return { action: 'CLOCK_RETARDED', new_offset_ms: this.virtualClockOffsetMs };
      }
      case 'NETWORK_TIMEOUT': {
        const err = new Error('ETIMEDOUT: connection timed out');
        err.code = 'ETIMEDOUT';
        throw err;
      }
      case 'PAYLOAD_CORRUPTION': {
        const payload = context.payload;
        if (typeof payload !== 'string') return payload;
        // Flip one character
        const idx = this.randomInt(0, payload.length - 1);
        const corrupted = payload.slice(0, idx) + 'X' + payload.slice(idx + 1);
        return corrupted;
      }
      case 'CONCURRENT_CONTENTION': {
        return { action: 'LOCK_CONTENTION_DELAY', delay_ms: this.randomInt(10, 100) };
      }
      default:
        throw new Error(`Unknown fault type: ${faultType}`);
    }
  }

  getCurrentTimeMs() {
    return Date.now() + this.virtualClockOffsetMs;
  }
}

module.exports = { ChaosEngine };
