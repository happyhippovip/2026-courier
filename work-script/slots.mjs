// Bounded execution slots: NORMAL max 1, TURBO max 2 app executions.
// Fake-worker tested only. Tabs, accounts or sub-agent counts create no slots.
// A slot is granted only after the caller's approval/capability/dependency
// checks; unknown sub-calls stay reported, never silently counted here.
export const DEFAULT_CAPACITIES = {NORMAL: 1, TURBO: 2};

export function createSlots({capacities = DEFAULT_CAPACITIES} = {}) {
  const held = new Map(); // mode -> Set(execId)
  return {
    capacity(mode) { return capacities[mode] ?? 0; },
    heldCount(mode) { return held.get(mode)?.size ?? 0; },
    acquire(mode, execId) {
      if (!Number.isInteger(capacities[mode])) return {granted: false, reason: 'unknown-mode'};
      if (typeof execId !== 'string' || !execId) return {granted: false, reason: 'no-identity'};
      let set = held.get(mode);
      if (!set) { set = new Set(); held.set(mode, set); }
      if (set.has(execId)) return {granted: true, duplicate: true};
      if (set.size >= capacities[mode]) return {granted: false, reason: 'slot-busy'};
      set.add(execId); // synchronous: exactly one winner per free slot
      return {granted: true};
    },
    release(mode, execId) {
      const set = held.get(mode);
      if (!set || !set.has(execId)) return {released: false};
      set.delete(execId);
      return {released: true};
    },
  };
}
