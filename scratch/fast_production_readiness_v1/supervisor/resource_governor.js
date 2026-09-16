// Per-Machine Resource Governor — Thermal & Pressure Guardrails
// Invariant: The thermal/resource problem is on MAC. Windows is healthy.
// Resource governance MUST be per-machine, NOT global.
// A hot Mac must NEVER throttle healthy Windows.

const { RESOURCE_STATE, RESOURCE_ACTION, DEFAULT_MACHINE_CONCURRENCY } = require('./types');

class MachineResourceGovernor {
  constructor(customConfigs = null) {
    this.machineConfigs = customConfigs || {
      MAC: {
        machine_id: 'MAC_CHIEF',
        machine_role: 'CHIEF_ORCHESTRATOR',
        os: 'darwin',
        max_concurrent_heavy: DEFAULT_MACHINE_CONCURRENCY.MAC.MAX_CONCURRENT_HEAVY_LOCAL_TASKS
      },
      WINDOWS: {
        machine_id: 'WINDOWS_WORKER',
        machine_role: 'HEAVY_BUILD_WORKER',
        os: 'windows',
        max_concurrent_heavy: DEFAULT_MACHINE_CONCURRENCY.WINDOWS.MAX_CONCURRENT_HEAVY_LOCAL_TASKS
      }
    };

    this.states = new Map();
    this._initializeDefaultStates();
  }

  _initializeDefaultStates() {
    for (const [key, cfg] of Object.entries(this.machineConfigs)) {
      this.states.set(cfg.machine_id, {
        machine_id: cfg.machine_id,
        machine_role: cfg.machine_role,
        os: cfg.os,
        max_concurrent_heavy: cfg.max_concurrent_heavy,
        active_heavy_tasks: 0,
        active_light_tasks: 0,
        cpu_load: 0.1,
        memory_pressure: 'NORMAL',
        swap_pressure: 'NORMAL',
        thermal_state_if_available: 'NORMAL',
        last_pressure_check: new Date().toISOString(),
        resource_state: RESOURCE_STATE.NORMAL,
        updated_at: new Date().toISOString()
      });
    }
  }

  getMachineState(machineId) {
    return this.states.get(machineId) || null;
  }

  updatePressure({
    machine_id,
    active_heavy_tasks = null,
    active_light_tasks = null,
    cpu_load = null,
    memory_pressure = null,
    swap_pressure = null,
    thermal_state = null
  }) {
    const s = this.states.get(machine_id);
    if (!s) throw new Error(`[GOVERNOR_ERROR] Machine '${machine_id}' not recognized`);

    if (active_heavy_tasks !== null) s.active_heavy_tasks = active_heavy_tasks;
    if (active_light_tasks !== null) s.active_light_tasks = active_light_tasks;
    if (cpu_load !== null) s.cpu_load = cpu_load;
    if (memory_pressure !== null) s.memory_pressure = memory_pressure;
    if (swap_pressure !== null) s.swap_pressure = swap_pressure;
    if (thermal_state !== null) s.thermal_state_if_available = thermal_state;

    s.last_pressure_check = new Date().toISOString();
    s.updated_at = s.last_pressure_check;

    // Classify machine resource state
    if (s.thermal_state_if_available === 'CRITICAL' || s.thermal_state_if_available === 'THERMAL_PRESSURE') {
      s.resource_state = RESOURCE_STATE.THERMAL_PRESSURE;
    } else if (s.cpu_load >= 0.90 || s.memory_pressure === 'HIGH' || s.swap_pressure === 'HIGH' || s.active_heavy_tasks >= s.max_concurrent_heavy) {
      s.resource_state = RESOURCE_STATE.PRESSURE;
    } else if (s.cpu_load >= 0.70 || s.active_heavy_tasks > 0) {
      s.resource_state = RESOURCE_STATE.BUSY;
    } else if (s.thermal_state_if_available === 'UNKNOWN') {
      s.resource_state = RESOURCE_STATE.UNKNOWN;
    } else {
      s.resource_state = RESOURCE_STATE.NORMAL;
    }

    return s;
  }

  evaluateTaskAdmission({
    machine_id,
    is_heavy_task = true
  }) {
    const s = this.states.get(machine_id);
    if (!s) throw new Error(`[GOVERNOR_ERROR] Machine '${machine_id}' not found`);

    // 1. Lightweight task check (read-only, inspection, status checks)
    if (!is_heavy_task) {
      if (s.resource_state === RESOURCE_STATE.THERMAL_PRESSURE && s.cpu_load > 0.95) {
        return {
          allowed: false,
          action: RESOURCE_ACTION.RECOVERY_MODE,
          reason: `Machine ${machine_id} is in critical recovery; light task held temporarily`
        };
      }
      return {
        allowed: true,
        action: RESOURCE_ACTION.ALLOW_LIGHT_ONLY,
        reason: `Light task permitted on ${machine_id}`
      };
    }

    // 2. Heavy task check
    // If machine is in THERMAL_PRESSURE or PRESSURE:
    if (s.resource_state === RESOURCE_STATE.THERMAL_PRESSURE || s.resource_state === RESOURCE_STATE.PRESSURE) {
      // Find if another machine is healthy
      const healthyTarget = this.findHealthyRerouteTarget(machine_id);
      return {
        allowed: false,
        action: healthyTarget ? RESOURCE_ACTION.RECOMMEND_REROUTE : RESOURCE_ACTION.HOLD_NEW_HEAVY,
        reroute_target_machine_id: healthyTarget,
        reason: `Machine ${machine_id} is under ${s.resource_state} (heavy tasks: ${s.active_heavy_tasks}/${s.max_concurrent_heavy}). New heavy tasks held.`
      };
    }

    // If active heavy tasks >= machine-specific limit
    if (s.active_heavy_tasks >= s.max_concurrent_heavy) {
      const healthyTarget = this.findHealthyRerouteTarget(machine_id);
      return {
        allowed: false,
        action: healthyTarget ? RESOURCE_ACTION.RECOMMEND_REROUTE : RESOURCE_ACTION.HOLD_NEW_HEAVY,
        reroute_target_machine_id: healthyTarget,
        reason: `Machine ${machine_id} reached heavy concurrency cap (${s.active_heavy_tasks}/${s.max_concurrent_heavy})`
      };
    }

    return {
      allowed: true,
      action: RESOURCE_ACTION.ALLOW,
      reason: `Machine ${machine_id} healthy and within capacity (${s.active_heavy_tasks}/${s.max_concurrent_heavy})`
    };
  }

  findHealthyRerouteTarget(pressuredMachineId) {
    for (const [id, state] of this.states.entries()) {
      if (id !== pressuredMachineId) {
        if (state.resource_state === RESOURCE_STATE.NORMAL || state.resource_state === RESOURCE_STATE.BUSY) {
          if (state.active_heavy_tasks < state.max_concurrent_heavy) {
            return id;
          }
        }
      }
    }
    return null;
  }
}

module.exports = {
  MachineResourceGovernor
};
