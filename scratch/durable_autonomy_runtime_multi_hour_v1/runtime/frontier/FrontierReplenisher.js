// Work Generator, Multi-Generator Low-Water Replenisher, and Saturation Challenger
const fs = require('fs');
const path = require('path');

class WorkGenerator {
  static generateCandidatesFromReservoir(reservoirPool, existingCandidateTitles = new Set()) {
    const generated = [];
    for (const item of reservoirPool) {
      if (!existingCandidateTitles.has(item.title)) {
        generated.push({
          title: item.title,
          category: item.category || 'ENGINEERING',
          priority: item.priority || 'P1',
          working_dir: item.working_dir,
          expected_information_gain: item.expected_information_gain || 8,
          unlocks_dependents_count: item.unlocks_dependents_count || 1,
          lane: item.lane || 'GENERAL',
          discovery_method: item.discovery_method || 'RESERVOIR_REPLENISHMENT',
          task_generator_fn: item.task_generator_fn
        });
        existingCandidateTitles.add(item.title);
      }
    }
    return generated;
  }
}

class FrontierReplenisher {
  constructor(frontier, reservoir = []) {
    this.frontier = frontier;
    this.reservoir = reservoir;
    this.seenTitles = new Set();
    this.generators = [];
    this.replenishCount = 0;
    this.laneCounts = {};

    this.initDefaultGenerators();
  }

  initDefaultGenerators() {
    const genDir = path.join(__dirname, 'generators');
    if (fs.existsSync(genDir)) {
      const files = fs.readdirSync(genDir).filter(f => f.endsWith('.js'));
      for (const file of files) {
        try {
          const mod = require(path.join(genDir, file));
          const GenClass = Object.values(mod)[0];
          if (typeof GenClass === 'function') {
            // Instantiate with default paths if needed
            const courierRoot = 'C:\\Users\\lol\\2026-workspace\\courier';
            const projectMemoryRoot = 'C:\\Users\\lol\\2026-workspace\\project-memory';
            const instance = new GenClass(courierRoot, projectMemoryRoot);
            this.registerGenerator(instance);
          }
        } catch (e) {
          console.error(`[FRONTIER-REPLENISHER] Failed loading generator ${file}:`, e.message);
        }
      }
    }
  }

  registerGenerator(generator) {
    this.generators.push(generator);
  }

  checkAndReplenish(activeGoal, runtime = null) {
    let addedCount = 0;

    if (this.frontier.needsReplenishment()) {
      console.log(`[FRONTIER-REPLENISHER] Low-water mark triggered! Ready count: ${this.frontier.getReadyCount()} < ${this.frontier.lowWaterMark}`);

      // 1. Replenish from reservoir if available
      if (this.reservoir && this.reservoir.length > 0) {
        const fromReservoir = WorkGenerator.generateCandidatesFromReservoir(this.reservoir, this.seenTitles);
        fromReservoir.forEach(item => {
          this.frontier.addCandidate({ ...item, goal_id: activeGoal.goal_id });
          addedCount++;
          this.recordLane(item.lane);
        });
      }

      // 2. If still below low-water mark (or to maintain reservoir breadth), invoke dynamic generators
      if (this.frontier.needsReplenishment() && this.generators.length > 0) {
        console.log(`[FRONTIER-REPLENISHER] Invoking ${this.generators.length} dynamic discovery generators...`);
        for (const gen of this.generators) {
          try {
            const dynamicCandidates = gen.generate(runtime || { missionRoot: path.resolve(__dirname, '../..') });
            for (const cand of dynamicCandidates) {
              if (!this.seenTitles.has(cand.title)) {
                this.seenTitles.add(cand.title);
                this.frontier.addCandidate({ ...cand, goal_id: activeGoal.goal_id });
                addedCount++;
                this.recordLane(cand.lane);
              }
            }
          } catch (err) {
            console.error('[FRONTIER-REPLENISHER] Generator execution error:', err.message);
          }
        }
      }

      if (addedCount > 0) {
        this.replenishCount++;
        console.log(`[FRONTIER-REPLENISHER] Replenished ${addedCount} candidates. Total ready: ${this.frontier.getReadyCount()}`);
        return { replenished: true, count: addedCount, new_ready_total: this.frontier.getReadyCount() };
      }
    }

    return { replenished: false, count: 0, ready_count: this.frontier.getReadyCount() };
  }

  recordLane(lane = 'GENERAL') {
    this.laneCounts[lane] = (this.laneCounts[lane] || 0) + 1;
  }
}

class SaturationChallenger {
  static challenge(frontier, completionGovernor) {
    const ready = frontier.getReadyCount();
    if (ready === 0) {
      return {
        saturated: false,
        reason: 'Saturation rejected: frontier depleted, but low-water replenishment or pause capacity required. Global saturation is disabled.',
        recommended_action: 'REPLENISH_OR_PAUSE_CAPACITY'
      };
    }
    return { saturated: false, ready_count: ready, reason: 'Active safe work exists on frontier.' };
  }
}

module.exports = {
  WorkGenerator,
  FrontierReplenisher,
  SaturationChallenger
};