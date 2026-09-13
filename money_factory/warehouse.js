// Opportunity Warehouse — Machine-Readable Single Source of Truth
// Lifecycle: SEED -> ACTIVE -> PROVING -> WINNER | ARCHIVED / KILLED
// Rules:
// 1. Ideas may be created, merged, mutated, demoted, archived, or killed.
// 2. NO idea is protected merely because it already exists.
// 3. Historical records are NEVER deleted; all mutations append immutable audit records.
// 4. Explicit UNKNOWN values when evidence is absent.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { MoneyScorer } = require('./scoring');

const LIFECYCLES = Object.freeze({
  SEED: 'SEED',
  ACTIVE: 'ACTIVE',
  PROVING: 'PROVING',
  WINNER: 'WINNER',
  ARCHIVED: 'ARCHIVED',
  KILLED: 'KILLED'
});

const REQUIRED_FIELDS = [
  'id',
  'version',
  'title',
  'status',
  'created_at',
  'updated_at',
  'source',
  'category',
  'revenue_probability',
  'expected_revenue_eur',
  'expected_profit_eur',
  'time_to_first_euro',
  'margin_estimate',
  'automation_score',
  'distribution_fit',
  'evidence_score',
  'capital_required_eur',
  'agent_hours_estimate',
  'human_minutes_estimate',
  'model_cost_estimate',
  'risk_score',
  'confidence',
  'channel_fit',
  'trend_evidence',
  'source_evidence',
  'next_test',
  'human_gates',
  'predicted_revenue_eur',
  'predicted_profit_eur',
  'actual_revenue_eur',
  'actual_profit_eur',
  'prediction_error',
  'promote_kill_reason'
];

function stringifyYaml(data) {
  if (Array.isArray(data)) {
    return data.map(item => {
      const lines = stringifyYamlItem(item, 2);
      return `- ${lines.trimStart()}`;
    }).join('\n');
  }
  return stringifyYamlItem(data, 0);
}

function stringifyYamlItem(obj, indent = 0) {
  const pad = ' '.repeat(indent);
  const out = [];
  for (const [k, v] of Object.entries(obj)) {
    if (v === null || v === undefined) {
      out.push(`${pad}${k}: null`);
    } else if (typeof v === 'object') {
      if (Array.isArray(v)) {
        if (v.length === 0) {
          out.push(`${pad}${k}: []`);
        } else {
          out.push(`${pad}${k}:`);
          for (const el of v) {
            if (typeof el === 'object') {
              out.push(`${pad}  -`);
              out.push(stringifyYamlItem(el, indent + 4));
            } else {
              out.push(`${pad}  - ${JSON.stringify(el)}`);
            }
          }
        }
      } else {
        out.push(`${pad}${k}:`);
        out.push(stringifyYamlItem(v, indent + 2));
      }
    } else if (typeof v === 'string') {
      if (v.includes('\n') || v.includes(':') || v === 'UNKNOWN' || v.includes('#')) {
        out.push(`${pad}${k}: ${JSON.stringify(v)}`);
      } else {
        out.push(`${pad}${k}: ${v}`);
      }
    } else {
      out.push(`${pad}${k}: ${v}`);
    }
  }
  return out.join('\n');
}

class OpportunityWarehouse {
  constructor(warehouseDir = null) {
    this.warehouseDir = warehouseDir || path.join(__dirname, '..', 'opportunity_warehouse');
    if (!fs.existsSync(this.warehouseDir)) {
      fs.mkdirSync(this.warehouseDir, { recursive: true });
    }

    this.yamlFile = path.join(this.warehouseDir, 'opportunities.yaml');
    this.jsonFile = path.join(this.warehouseDir, 'opportunities.json');
    this.historyFile = path.join(this.warehouseDir, 'history_ledger.json');

    this.opportunities = new Map();
    this.historyLedger = [];

    this._load();
  }

  _load() {
    if (fs.existsSync(this.jsonFile)) {
      try {
        const raw = JSON.parse(fs.readFileSync(this.jsonFile, 'utf8'));
        if (Array.isArray(raw)) {
          for (const item of raw) {
            if (item.version === undefined) item.version = 1;
            this.opportunities.set(item.id, item);
          }
        }
      } catch (err) {
        console.error(`[WAREHOUSE] Warning: Failed to load ${this.jsonFile}:`, err.message);
      }
    }

    if (fs.existsSync(this.historyFile)) {
      try {
        const raw = JSON.parse(fs.readFileSync(this.historyFile, 'utf8'));
        if (Array.isArray(raw)) {
          this.historyLedger = raw;
        }
      } catch (err) {
        console.error(`[WAREHOUSE] Warning: Failed to load ${this.historyFile}:`, err.message);
      }
    }
  }

  _persist() {
    const list = Array.from(this.opportunities.values());

    // 1. Persist JSON
    const tmpJson = `${this.jsonFile}.tmp`;
    fs.writeFileSync(tmpJson, JSON.stringify(list, null, 2), 'utf8');
    fs.renameSync(tmpJson, this.jsonFile);

    // 2. Persist YAML
    const tmpYaml = `${this.yamlFile}.tmp`;
    fs.writeFileSync(tmpYaml, stringifyYaml(list), 'utf8');
    fs.renameSync(tmpYaml, this.yamlFile);

    // 3. Persist History Ledger
    const tmpHist = `${this.historyFile}.tmp`;
    fs.writeFileSync(tmpHist, JSON.stringify(this.historyLedger, null, 2), 'utf8');
    fs.renameSync(tmpHist, this.historyFile);
  }

  _recordEvent(eventType, opportunityId, details, snapshot = null) {
    const record = {
      event_id: `EVT-${Date.now()}-${crypto.randomBytes(3).toString('hex')}`,
      timestamp: new Date().toISOString(),
      event_type: eventType,
      opportunity_id: opportunityId,
      details,
      snapshot: snapshot ? JSON.parse(JSON.stringify(snapshot)) : null
    };
    this.historyLedger.push(record);
  }

  validateSchema(opp) {
    const missing = [];
    for (const f of REQUIRED_FIELDS) {
      if (opp[f] === undefined) {
        missing.push(f);
      }
    }
    if (missing.length > 0) {
      throw new Error(`[WAREHOUSE_SCHEMA_ERROR] Opportunity '${opp.id || 'UNKNOWN'}' missing mandatory fields: ${missing.join(', ')}`);
    }
    if (!Object.values(LIFECYCLES).includes(opp.status)) {
      throw new Error(`[WAREHOUSE_SCHEMA_ERROR] Invalid status '${opp.status}' for opportunity '${opp.id}'. Must be one of: ${Object.values(LIFECYCLES).join(', ')}`);
    }
    return true;
  }

  addOpportunity(rawOpp) {
    const opp = { ...rawOpp };
    // Defaults for missing optional evidence fields to explicit UNKNOWN
    if (opp.source_evidence === undefined) opp.source_evidence = 'UNKNOWN';
    if (opp.trend_evidence === undefined) opp.trend_evidence = 'UNKNOWN';
    if (opp.prediction_error === undefined) opp.prediction_error = 'UNKNOWN';
    if (opp.promote_kill_reason === undefined) opp.promote_kill_reason = 'UNKNOWN';
    if (!opp.created_at) opp.created_at = new Date().toISOString();
    if (!opp.updated_at) opp.updated_at = new Date().toISOString();
    if (!opp.status) opp.status = LIFECYCLES.SEED;
    if (opp.version === undefined) opp.version = 1;

    this.validateSchema(opp);

    // Idempotency: If exact same ID and same core content exists, no-op
    if (this.opportunities.has(opp.id)) {
      const existing = this.opportunities.get(opp.id);
      if (!rawOpp.created_at) opp.created_at = existing.created_at;
      if (!rawOpp.updated_at) opp.updated_at = existing.updated_at;
      if (rawOpp.version === undefined) opp.version = existing.version;
      const existingClone = { ...existing };
      delete existingClone.score;
      const oppClone = { ...opp };
      delete oppClone.score;
      if (JSON.stringify(existingClone) === JSON.stringify(oppClone)) {
        return { status: 'IDEMPOTENT_NOOP', opportunity: existing };
      }
    }

    // Attach deterministic score
    opp.score = MoneyScorer.computeScore(opp);

    this.opportunities.set(opp.id, opp);
    this._recordEvent('OPPORTUNITY_CREATED', opp.id, { reason: 'Ingested into warehouse' }, opp);
    this._persist();

    return { status: 'CREATED', opportunity: opp };
  }

  getOpportunity(id) {
    return this.opportunities.get(id) || null;
  }

  getAllOpportunities() {
    return Array.from(this.opportunities.values());
  }

  getHistory(opportunityId = null) {
    if (opportunityId) {
      return this.historyLedger.filter(e => e.opportunity_id === opportunityId);
    }
    return [...this.historyLedger];
  }

  mutateOpportunity(id, patch, reason = 'Economic parameter update') {
    const existing = this.opportunities.get(id);
    if (!existing) throw new Error(`[WAREHOUSE_ERROR] Cannot mutate '${id}': not found.`);

    const priorSnapshot = JSON.parse(JSON.stringify(existing));
    const nextVersion = (existing.version || 1) + 1;
    const updated = {
      ...existing,
      ...patch,
      id, // Cannot change ID
      version: nextVersion,
      created_at: existing.created_at, // Preserve created_at
      updated_at: new Date().toISOString()
    };

    updated.score = MoneyScorer.computeScore(updated);
    this.validateSchema(updated);

    this.opportunities.set(id, updated);
    this._recordEvent('OPPORTUNITY_MUTATED', id, { reason, patch }, priorSnapshot);
    this._persist();

    return updated;
  }

  promoteOpportunity(id, targetLifecycle, reason, evidenceArtifact = null) {
    const existing = this.opportunities.get(id);
    if (!existing) throw new Error(`[WAREHOUSE_ERROR] Cannot promote '${id}': not found.`);

    if (existing.status === LIFECYCLES.KILLED) {
      throw new Error(`[WAREHOUSE_ERROR] Cannot promote killed opportunity '${id}' without explicit unkilling.`);
    }

    // Evidence checks for transitions
    if (targetLifecycle === LIFECYCLES.ACTIVE) {
      if (!reason || reason.trim().length < 5) {
        throw new Error(`[GATE_ERROR] SEED -> ACTIVE promotion requires substantive rationale.`);
      }
    } else if (targetLifecycle === LIFECYCLES.PROVING) {
      if (existing.evidence_score === 'UNKNOWN' || Number(existing.evidence_score) < 0.20) {
        throw new Error(`[GATE_ERROR] ACTIVE -> PROVING promotion requires minimum evidence score 0.20.`);
      }
    } else if (targetLifecycle === LIFECYCLES.WINNER) {
      if (existing.actual_revenue_eur <= 0) {
        throw new Error(`[GATE_ERROR] PROVING -> WINNER promotion strictly requires verified actual_revenue_eur > 0.`);
      }
    }

    return this.mutateOpportunity(id, {
      status: targetLifecycle,
      promote_kill_reason: reason,
      evidence_artifact: evidenceArtifact || existing.evidence_artifact || 'UNKNOWN'
    }, `Promoted to ${targetLifecycle}: ${reason}`);
  }

  demoteOpportunity(id, targetLifecycle, reason) {
    const existing = this.opportunities.get(id);
    if (!existing) throw new Error(`[WAREHOUSE_ERROR] Cannot demote '${id}': not found.`);

    return this.mutateOpportunity(id, {
      status: targetLifecycle,
      promote_kill_reason: reason
    }, `Demoted to ${targetLifecycle}: ${reason}`);
  }

  mergeOpportunities(primaryId, secondaryId, mergeRationale) {
    const p = this.opportunities.get(primaryId);
    const s = this.opportunities.get(secondaryId);
    if (!p || !s) throw new Error(`[WAREHOUSE_ERROR] Cannot merge: one or both IDs not found.`);

    const snapshotSecondary = JSON.parse(JSON.stringify(s));

    // Secondary gets archived with MERGED reference
    this.mutateOpportunity(secondaryId, {
      status: LIFECYCLES.ARCHIVED,
      promote_kill_reason: `Merged into ${primaryId}: ${mergeRationale}`
    }, `Merged into ${primaryId}`);

    // Primary gets updated notes and sources
    const updated = this.mutateOpportunity(primaryId, {
      source_evidence: `${p.source_evidence}; MERGED_FROM(${secondaryId})`
    }, `Incorporated merged candidate ${secondaryId}`);

    this._recordEvent('OPPORTUNITIES_MERGED', primaryId, {
      merged_with: secondaryId,
      rationale: mergeRationale
    }, snapshotSecondary);

    return updated;
  }

  archiveOpportunity(id, reason) {
    return this.demoteOpportunity(id, LIFECYCLES.ARCHIVED, reason);
  }

  killOpportunity(id, killReason) {
    if (!killReason || killReason.trim().length < 5) {
      throw new Error(`[WAREHOUSE_ERROR] Killing an opportunity requires an explicit, substantive reason.`);
    }
    return this.mutateOpportunity(id, {
      status: LIFECYCLES.KILLED,
      promote_kill_reason: killReason
    }, `Killed: ${killReason}`);
  }
}

module.exports = {
  LIFECYCLES,
  REQUIRED_FIELDS,
  stringifyYaml,
  OpportunityWarehouse
};
