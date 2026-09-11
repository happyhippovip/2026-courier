const assert = require('assert');
const { SchemaExtractor } = require('../lib/schema_extractor');
const { EnvSwitcher } = require('../lib/env_switcher');

console.log('--- TEST 1: Schema Extraction with Vector Columns ---');
const sampleSupabaseDDL = `
CREATE TABLE agent_memories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id text NOT NULL,
  content text NOT NULL,
  embedding vector(1536) NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_memories_embedding ON agent_memories USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
`;

const extractor = new SchemaExtractor();
const summary = extractor.parseDDL(sampleSupabaseDDL);

assert.strictEqual(summary.tableCount, 1);
assert.strictEqual(summary.tables[0].name, 'agent_memories');
assert.strictEqual(summary.vectorColumnCount, 1);
assert.strictEqual(summary.vectorColumns[0].column, 'embedding');
assert.strictEqual(summary.vectorColumns[0].dimensions, 1536);
assert.strictEqual(summary.indexCount, 1);
assert.strictEqual(summary.indexes[0].method, 'hnsw');
console.log('PASS [Test 1]: SchemaExtractor accurately parses tables, vector dimensions, and HNSW indexes.');

console.log('--- TEST 2: Local PostgreSQL DDL Generation ---');
const localDDL = extractor.generateLocalDDL('local_agent_db');
assert(localDDL.includes('CREATE EXTENSION IF NOT EXISTS "vector";'), 'Must include vector extension');
assert(localDDL.includes('CREATE TABLE IF NOT EXISTS agent_memories'), 'Must include table');
assert(localDDL.includes('USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);'), 'Must preserve HNSW params');
console.log('PASS [Test 2]: Local DDL properly incorporates vector extension and tuned parameters.');

console.log('--- TEST 3: Docker-Compose Configuration Generation ---');
const compose = EnvSwitcher.generateDockerCompose({ port: 5433, dbName: 'agent_test_db' });
assert(compose.includes('image: pgvector/pgvector:pg16'));
assert(compose.includes('"5433:5432"'));
assert(compose.includes('POSTGRES_DB: agent_test_db'));
assert(compose.includes('shared_buffers=512MB'));
console.log('PASS [Test 3]: Docker-compose template provides tuned local PG16 with pgvector.');

console.log('--- TEST 4: Environment Switcher (.env Rewriter) ---');
const cloudEnv = [
  '# Production Supabase config',
  'DATABASE_URL="postgres://postgres.abc:pass@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"',
  'NEXT_PUBLIC_SUPABASE_URL="https://abc.supabase.co"',
  'OPENAI_API_KEY="sk-test"'
].join('\n');

const localEnv = EnvSwitcher.switchConnection({ envContent: cloudEnv, targetMode: 'local', localPort: 5433, dbName: 'agent_test_db' });
assert(localEnv.includes('DATABASE_URL="postgresql://postgres:postgres@localhost:5433/agent_test_db"'));
assert(localEnv.includes('# NEXT_PUBLIC_SUPABASE_URL='));
assert(localEnv.includes('OPENAI_API_KEY="sk-test"'));
console.log('PASS [Test 4]: EnvSwitcher cleanly redirects database connection to local instance.');

console.log('--- TEST 5: Fail-Closed Invalid Input Rejection ---');
assert.throws(() => extractor.parseDDL(''), /SCHEMA_EXTRACTOR_ERROR/, 'Empty string must throw');
assert.throws(() => extractor.parseDDL(null), /SCHEMA_EXTRACTOR_ERROR/, 'Null input must throw');
console.log('PASS [Test 5]: Invalid inputs fail closed.');

console.log('\n>>> ALL 5 pgvector-local-kit PROTOTYPE TESTS PASS (100% DETERMINISTIC) <<<');
