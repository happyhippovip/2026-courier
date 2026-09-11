/**
 * Adaptive Token Budget PID Controller & Context Oscillation Damper
 * Implements a Proportional-Integral-Derivative (PID) control loop over agent context budgets,
 * damping aggressive pruning oscillations and smoothly converging token counts to setpoint limits.
 */

class PidBudgetController {
  constructor(kp = 0.5, ki = 0.1, kd = 0.2) {
    this.kp = kp; // Proportional gain
    this.ki = ki; // Integral gain
    this.kd = kd; // Derivative gain
    this.integral = 0;
    this.lastError = 0;
  }

  computeControlSignal(currentTokens, setpointTokens, dt = 1.0) {
    // Error: positive when over budget, negative when under budget
    const error = currentTokens - setpointTokens;

    // Proportional term
    const pTerm = this.kp * error;

    // Integral term with anti-windup clamping
    this.integral += error * dt;
    const maxIntegral = setpointTokens * 0.5;
    this.integral = Math.max(-maxIntegral, Math.min(maxIntegral, this.integral));
    const iTerm = this.ki * this.integral;

    // Derivative term (rate of change of error)
    const derivative = (error - this.lastError) / dt;
    const dTerm = this.kd * derivative;
    this.lastError = error;

    // Total control signal (unbounded)
    const rawSignal = pTerm + iTerm + dTerm;

    // Normalize to prune aggressiveness ratio between 0.0 (no pruning) and 1.0 (maximum pruning)
    const normalizedRatio = Math.max(0.0, Math.min(1.0, rawSignal / (setpointTokens * 0.5)));

    return {
      currentTokens,
      setpointTokens,
      error,
      pTerm: Number(pTerm.toFixed(2)),
      iTerm: Number(iTerm.toFixed(2)),
      dTerm: Number(dTerm.toFixed(2)),
      rawSignal: Number(rawSignal.toFixed(2)),
      pruneAggressiveness: Number(normalizedRatio.toFixed(3))
    };
  }

  reset() {
    this.integral = 0;
    this.lastError = 0;
  }
}

module.exports = { PidBudgetController };