const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { SbomAuditor } = require('../lib/sbom_generator');

console.log('Testing SbomAuditor...');

const auditor = new SbomAuditor();

// Test 1: File hashing
const tempTestFile = path.join(__dirname, 'temp_test_hash.txt');
fs.writeFileSync(tempTestFile, 'Test content for SHA256 hashing');
const hash = auditor.hashFile(tempTestFile);
assert.strictEqual(typeof hash, 'string');
assert.strictEqual(hash.length, 64);
fs.unlinkSync(tempTestFile);

// Test 2: Non-existent file hashing returns null
assert.strictEqual(auditor.hashFile('non_existent_file_xyz.txt'), null);

// Test 3: Generate SBOM
const sbom = auditor.generateSbom(__dirname, ['test_sbom_generator.js']);
assert.strictEqual(sbom.bomFormat, 'CycloneDX');
assert.strictEqual(sbom.metadata.component.name, 'agent-context-trimmer');
assert.strictEqual(sbom.metadata.securityAudit.externalRuntimeDependencies, 0);
assert.strictEqual(sbom.components.length, 1);

// Test 4: Verify component metadata
assert.strictEqual(sbom.components[0].hashes[0].algorithm, 'SHA-256');
assert.ok(sbom.stats.totalSizeBytes > 0);

console.log('All SbomAuditor tests passed (4/4)!');
